# pyre-ignore-all-errors
from fastapi import FastAPI, Query, HTTPException, Depends, UploadFile, File # pyre-ignore
from fastapi.responses import StreamingResponse # pyre-ignore
from fastapi.middleware.cors import CORSMiddleware # pyre-ignore
from sqlalchemy.orm import Session # pyre-ignore
from sqlalchemy import func # pyre-ignore
from pydantic import BaseModel # pyre-ignore
import logging

logger = logging.getLogger(__name__)
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict

from database import engine, SessionLocal, Base, PaperModel, get_db # pyre-ignore
from arxiv_ingest import ingest_by_year # pyre-ignore
from ranking import score_and_filter, compute_term_frequencies # pyre-ignore
from query_parser import parse_query # pyre-ignore
from analytics import find_gaps # pyre-ignore
from llm_layer import ( # pyre-ignore
    llm_filter_irrelevant, 
    llm_rerank, 
    quick_summary, 
    literature_review_llm, 
    explain_trend_llm, 
    why_this_paper,
    parse_query_llm,
    paper_explain,
    generate_gap_sentences
)
from ranking import strict_filter, score_and_filter, compute_term_frequencies # pyre-ignore
from embeddings import build_index, semantic_search # pyre-ignore
from chat_engine import chat_with_papers, clear_session # pyre-ignore

# Initialize DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="ResearchIQ Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------------------------
# Input Models
# -------------------------------------------------------------------
class ResearchQuery(BaseModel):
    topic: str
    purpose: str  # "literature review", "quick overview", "deep dive"
    num_papers: int = 50

# -------------------------------------------------------------------
# Core Endpoints
# -------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/papers/arxiv")
def get_arxiv_papers(query: str = Query("ai"), max_results: int = Query(50)):
    from query_parser import normalize
    parsed = parse_query(query)
    res = ingest_by_year(normalize(query), start_year=2018, end_year=2026)
    return res


def diversify(papers: list, num: int) -> list:
    by_year: dict = {}
    for p in papers:
        y = p.year or 0
        by_year.setdefault(y, []).append(p)

    result = []
    years = sorted(by_year.keys())

    while len(result) < num:
        for y in years:
            if by_year[y]:
                result.append(by_year[y].pop(0))
                if len(result) >= num:
                    break
        # Stop if all buckets are empty
        if all(len(lst) == 0 for lst in by_year.values()):
            break
            
    return result

@app.post("/research/query")
def research_query(req: ResearchQuery, db: Session = Depends(get_db)):
    # 1. LLM Query Parser
    parsed = parse_query_llm(req.topic)
    source = "db"
    is_fallback = False

    core_query = " ".join(parsed.get("core_terms", [])) or req.topic
    term_count = len([t for t in core_query.split() if len(t) > 2])
    # 1 word -> 1 match required (score >= 1). Multi-word -> score >= 2.
    required_score = 1 if term_count <= 1 else 2
    
    # helper to evaluate relevance
    def get_good_candidates():
        all_p = db.query(PaperModel).all()
        from arxiv_ingest import score_paper  # pyre-ignore
        scored = []
        for p in all_p:
            s_score = score_paper({"title": p.title, "abstract": p.abstract}, core_query)
            if s_score >= required_score:
                scored.append((p, s_score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored]
        
    def save_dicts_to_db(dicts_list, p_source):
        added = 0
        from keyword_extractor import extract_keywords  # pyre-ignore
        for d in dicts_list:
            try:
                if db.query(PaperModel).filter_by(id=d["id"]).first(): continue
                kw = extract_keywords(d["title"]) or [w for w in d["title"].lower().split() if len(w)>3][:3]
                pm = PaperModel(
                    id=d["id"], title=d["title"], abstract=d.get("abstract", ""),
                    authors=d.get("authors", []), year=d.get("year", 2024),
                    source=p_source, published=None,
                    domains=[req.topic], keywords=kw, citation_count=d.get("citation_count", 0)
                )
                db.add(pm)
                added += 1
            except Exception as e:
                db.rollback()
                print(f"[SAVE] Error saving paper {d.get('id','?')}: {e}")
                continue
        try:
            if added > 0: db.commit()
        except Exception as e:
            db.rollback()
            print(f"[SAVE] Commit failed: {e}")
            added = 0
        return added

    # 1. Local Cache
    candidates = get_good_candidates()
    print(f"[CASCADE] Step 1 - Local DB: {len(candidates)} candidates for '{core_query}'")

    # 2. S2 API
    if len(candidates) < req.num_papers:
        try:
            print(f"[CASCADE] Step 2 - Calling Semantic Scholar API...")
            from arxiv_ingest import ingest_quick_s2  # pyre-ignore
            s2_result = ingest_quick_s2(core_query, 30)
            s2_added = s2_result.get("added", 0)
            print(f"[CASCADE] Step 2 - S2 added {s2_added} papers")
            if s2_added > 0:
                source = "S2 API"
                candidates = get_good_candidates()
                print(f"[CASCADE] Step 2 - After S2: {len(candidates)} candidates")
        except Exception as e:
            print(f"[CASCADE] Step 2 - S2 FAILED: {e}")

    # 3. OpenAlex (ALWAYS called if we need more papers)
    if len(candidates) < req.num_papers:
        try:
            print(f"[CASCADE] Step 3 - Calling OpenAlex API...")
            from arxiv_ingest import fetch_openalex  # pyre-ignore
            oa_results = fetch_openalex(core_query, 20)
            print(f"[CASCADE] Step 3 - OpenAlex returned {len(oa_results)} raw results")
            if oa_results:
                oa_added = save_dicts_to_db(oa_results, "openalex")
                print(f"[CASCADE] Step 3 - OpenAlex saved {oa_added} new papers to DB")
                source += " + OpenAlex" if source else "OpenAlex"
                candidates = get_good_candidates()
                print(f"[CASCADE] Step 3 - After OpenAlex: {len(candidates)} candidates")
        except Exception as e:
            print(f"[CASCADE] Step 3 - OpenAlex FAILED: {e}")

    # 4. CrossRef (ALWAYS called if we need more papers)
    if len(candidates) < req.num_papers:
        try:
            print(f"[CASCADE] Step 4 - Calling CrossRef API...")
            from arxiv_ingest import fetch_crossref  # pyre-ignore
            cr_results = fetch_crossref(core_query, 15)
            print(f"[CASCADE] Step 4 - CrossRef returned {len(cr_results)} raw results")
            if cr_results:
                cr_added = save_dicts_to_db(cr_results, "crossref")
                print(f"[CASCADE] Step 4 - CrossRef saved {cr_added} new papers to DB")
                source += " + CrossRef"
                candidates = get_good_candidates()
                print(f"[CASCADE] Step 4 - After CrossRef: {len(candidates)} candidates")
        except Exception as e:
            print(f"[CASCADE] Step 4 - CrossRef FAILED: {e}")

    # 5. Relaxed scoring: if strict scoring yielded < 3, try scoring >= 1
    if len(candidates) < 3:
        print(f"[CASCADE] Step 5 - Relaxing score threshold to 1...")
        from arxiv_ingest import score_paper as _sp  # pyre-ignore
        all_p = db.query(PaperModel).all()
        relaxed = []
        for p in all_p:
            s = _sp({"title": p.title, "abstract": p.abstract}, core_query)
            if s >= 1:
                relaxed.append((p, s))
        relaxed.sort(key=lambda x: x[1], reverse=True)
        candidates = [p for p, _ in relaxed[:req.num_papers]]
        source += " + Relaxed"
        print(f"[CASCADE] Step 5 - After relaxed scoring: {len(candidates)} candidates")

    # 6. Broad tokenized fallback (any single keyword match)
    if len(candidates) < 3:
        try:
            print(f"[CASCADE] Step 6 - Broad tokenized DB search...")
            from arxiv_ingest import fallback_db_search  # pyre-ignore
            fallback_candidates = fallback_db_search(req.topic, db, limit=20)
            if fallback_candidates:
                # Merge without duplicates
                existing_ids = {getattr(c, 'id', None) for c in candidates}
                for fc in fallback_candidates:
                    if getattr(fc, 'id', None) not in existing_ids:
                        candidates.append(fc)
                source += " + DB Fallback"
                print(f"[CASCADE] Step 6 - After DB fallback: {len(candidates)} candidates")
        except Exception as e:
            print(f"[CASCADE] Step 6 - DB Fallback FAILED: {e}")

    # 7. Absolute last resort — return ANY papers with at least 1 keyword match
    if len(candidates) < 3:
        print(f"[CASCADE] Step 7 - EMERGENCY: returning any partially matching papers")
        terms = [t.lower() for t in core_query.split() if len(t) > 2]
        all_p = db.query(PaperModel).all()
        emergency = []
        for p in all_p:
            text = ((p.title or "") + " " + (p.abstract or "")).lower()
            if any(t in text for t in terms):
                emergency.append(p)
        if emergency:
            candidates = emergency[:max(req.num_papers, 5)]
        else:
            # True last resort: return most recent papers
            candidates = db.query(PaperModel).order_by(
                PaperModel.citation_count.desc()
            ).limit(max(req.num_papers, 5)).all()
        source = "Emergency Fallback"
        is_fallback = True
        print(f"[CASCADE] Step 7 - Emergency: {len(candidates)} candidates")

    logger.info(f"QUERY: {req.topic} | PARSED: {parsed} | MATCHED: {len(candidates)} | SOURCE: {source}")

    if len(candidates) == 0:
        return {
            "topic": req.topic,
            "purpose": req.purpose,
            "count": 0,
            "papers": [],
            "summary": "No papers available in database. Please seed data first.",
            "status": "complete",
            "source": source,
            "fallback": True,
            "parsed_query": parsed
        }

    # 6. Ranking layer
    from ranking import rank_papers  # pyre-ignore
    ranked_with_scores = rank_papers(candidates, req.topic, limit=req.num_papers)

    # Build response papers
    response_papers = []
    core_terms = parsed.get("core_terms", [])
    context_terms = parsed.get("context_terms", [])
    all_search_terms = core_terms + context_terms

    for p, rank_score in ranked_with_scores:
        text = ((p.title or "") + " " + (p.abstract or "")).lower()
        matched_keywords = [t for t in all_search_terms if t in text]

        # Use rank_score as the primary display score (0-100)
        confidence = int(rank_score * 100)

        reasons = []
        core_matches = [t for t in core_terms if t in text]
        context_matches = [t for t in context_terms if t in text]
        if core_matches:
            reasons.append(f"Core: {', '.join(core_matches)}")
        if context_matches:
            reasons.append(f"Context: {', '.join(context_matches)}")
        llm_reason = " | ".join(reasons) if reasons else "Semantic match"

        response_papers.append({
            "title": p.title,
            "year": p.year,
            "authors": p.authors,
            "abstract": p.abstract,
            "matched_keywords": matched_keywords,
            "score": confidence,
            "id": p.id,
            "llm_reason": llm_reason
        })

    return {
        "topic": req.topic,
        "purpose": req.purpose,
        "count": len(response_papers),
        "papers": response_papers,
        "summary": None,
        "status": "processing",
        "source": source,
        "fallback": is_fallback,
        "parsed_query": parsed
    }

class AnalysisRequest(BaseModel):
    topic: str
    purpose: str
    paper_ids: List[str]

@app.post("/analytics/analysis")
def generate_analysis(req: AnalysisRequest, db: Session = Depends(get_db)):
    papers = db.query(PaperModel).filter(PaperModel.id.in_(req.paper_ids)).all()
    
    papers_dict = {p.id: p for p in papers}
    ordered_papers = [papers_dict[pid] for pid in req.paper_ids if pid in papers_dict]
    
    summary_text = None
    if req.purpose == "quick overview":
        summary_text = quick_summary(req.topic, ordered_papers[:5])
    elif req.purpose == "literature review":
        rev = literature_review_llm(req.topic, ordered_papers[:10])
        summary_text = rev.get("summary", "Summary not generated.")
    else:
        summary_text = quick_summary(req.topic, ordered_papers[:5])

    # Generate LLM gap sentences
    gaps = generate_gap_sentences(req.topic, ordered_papers) if ordered_papers else []
        
    return {
        "summary": summary_text,
        "gaps": gaps,
        "status": "complete"
    }

# -------------------------------------------------------------------
# Chat Endpoint (LangChain-powered)
# -------------------------------------------------------------------
class ChatRequest(BaseModel):
    query: str
    papers: List[Dict[str, Any]] = []
    session_id: str = "default"

@app.post("/upload-paper")
async def upload_paper(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Absolute Failsafe Upload Mode.
    Extracts text from PDF, builds a synthetic PaperModel, and returns a dashboard-ready response.
    """
    import fitz  # PyMuPDF
    import tempfile
    import os
    
    # 1. Save and extract
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf", mode="wb") as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
        
    try:
        doc = fitz.open(tmp_path)
        text_pages = []
        for i in range(min(3, len(doc))):  # Extract first 3 pages
            text_pages.append(doc[i].get_text())
        full_text = "\n".join(text_pages)
        title = file.filename.replace(".pdf", "")
        # Very simple abstract extraction heuristic: take first 1500 chars
        abstract = full_text[:1500].replace("\n", " ").strip()
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

    # 2. Build synthetic paper
    import time
    from keyword_extractor import extract_keywords # pyre-ignore
    paper_id = f"upload_{int(time.time())}"
    kw = extract_keywords(title) or [w for w in title.lower().split() if len(w)>3][:3]
    
    pm = PaperModel(
        id=paper_id,
        title=title,
        abstract=abstract,
        authors=["Uploaded User"],
        year=datetime.now().year,
        source="upload",
        domains=[title],
        keywords=kw,
        citation_count=0
    )
    db.add(pm)
    db.commit()

    # 3. Return UI-ready dashboard response
    response_papers = [{
        "title": pm.title,
        "year": pm.year,
        "authors": pm.authors,
        "abstract": pm.abstract,
        "matched_keywords": kw,
        "score": 100,
        "id": pm.id,
        "llm_reason": "Direct Upload"
    }]

    return {
        "topic": title,
        "purpose": "deep dive",
        "count": 1,
        "papers": response_papers,
        "summary": None,
        "status": "processing",
        "source": "upload",
        "fallback": True,
        "parsed_query": {"core_terms": kw, "context_terms": []}
    }
def chat_query(req: ChatRequest):
    result = chat_with_papers(req.query, req.papers, req.session_id)
    return result

@app.post("/chat/clear")
def chat_clear(session_id: str = "default"):
    clear_session(session_id)
    return {"status": "cleared"}

# -------------------------------------------------------------------
# Paper-Level Analysis
# -------------------------------------------------------------------
class PaperAnalyzeRequest(BaseModel):
    paper_id: str

@app.post("/paper/analyze")
def analyze_paper(req: PaperAnalyzeRequest, db: Session = Depends(get_db)):
    paper = db.query(PaperModel).filter(PaperModel.id == req.paper_id).first()
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    
    result = paper_explain(paper)
    
    return {"result": result}


@app.get("/analytics/keyword-trend")
def keyword_trend(keyword: str):
    db: Session = SessionLocal()
    data: Dict[int, int] = defaultdict(int)

    papers = db.query(PaperModel).all()
    current_year = datetime.now().year

    for p in papers:
        if not p.year:
            continue
            
        try:
            year_val = int(p.year)
        except (ValueError, TypeError):
            continue
            
        # Hard limits against hallucinations: 
        # Don't track papers claiming to be from the future or impossibly old
        if year_val < 1950 or year_val > current_year + 1:
            continue

        text = f"{p.title or ''} {p.abstract or ''}".lower()
        keyword_lower = keyword.lower()
        
        # Stricter keyword match (whole word or highly indicative)
        import re
        if re.search(r'\b' + re.escape(keyword_lower) + r'\b', text):
            data[year_val] += 1
            
    db.close()

    if not data:
        return []

    sorted_dict = dict(sorted(data.items()))
    return [{"year": k, "count": v} for k, v in sorted_dict.items()]

@app.get("/export/tableau-data")
def export_data():
    db = SessionLocal()
    papers = db.query(PaperModel).all()
    db.close()

    return [
        {
            "title": p.title,
            "year": p.year,
            "authors": ", ".join(p.authors or []),
            "keywords": ", ".join(p.keywords or []),
            "domain": ", ".join(p.domains or []),
            "source": getattr(p, "source", "arxiv"),
            "score": getattr(p, "score", 0),
            "abstract": p.abstract
        }
        for p in papers if p.year and p.year >= 2015
    ]

@app.get("/export/tableau-aggregates")
def export_aggregates():
    db = SessionLocal()
    results = (
        db.query(PaperModel.year, func.count(PaperModel.id))
        .group_by(PaperModel.year)
        .order_by(PaperModel.year)
        .all()
    )
    db.close()

    return [{"year": y, "count": c} for y, c in results]

# -------------------------------------------------------------------
# Intelligence Features
# -------------------------------------------------------------------
def extract_top_keywords(papers: list) -> List[str]:
    from collections import Counter
    keywords = []
    for p in papers:
        if p.keywords:
            keywords.extend(p.keywords)
    return [k for k, _ in Counter(keywords).most_common(8)]

@app.get("/analytics/literature-review")
def literature_review(domain: str = Query(...), db: Session = Depends(get_db)):
    parsed = parse_query(domain)
    all_papers = db.query(PaperModel).all()
    scored = score_and_filter(all_papers, parsed)
    
    top_papers = [x[0] for x in scored[:50]]
    if not top_papers:
        top_papers = list(all_papers[:50])
    
    # Replace static parsing with LLM structured parsing
    rev = literature_review_llm(domain, top_papers)
    
    # Fallback missing data if needed
    if not rev.get("summary"):
        rev["summary"] = "No detailed abstracts available to summarize."
        
    return {
        "summary": rev.get("summary"),
        "key_themes": rev.get("key_themes", extract_top_keywords(top_papers)),
        "recent_trends": extract_top_keywords(top_papers[:20]),
        "open_questions": rev.get("open_questions", []),
        "top_papers": [{"title": p.title, "year": p.year} for p in top_papers[:10]]
    }

@app.get("/analytics/trend-explanation")
def trend_explanation(keyword: str = Query(...), db: Session = Depends(get_db)):
    db_session: Session = SessionLocal()
    data: Dict[int, int] = defaultdict(int)

    papers = db_session.query(PaperModel).all()
    for p in papers:
        if not p.year:
            continue
        text = f"{p.title or ''} {p.abstract or ''}".lower()
        if keyword.lower() in text:
            data[p.year] += 1
    db_session.close()

    if len(data) < 3:
        return {"keyword": keyword, "spike_year": None, "explanation": "Not enough data to explain trend for this topic."}
         
    spike_year = max(list(data.keys()), key=lambda y: data[y])
    
    parsed = parse_query(keyword)
    all_papers = db.query(PaperModel).filter(PaperModel.year == spike_year).all()
    term_freq = compute_term_frequencies(all_papers)
    scored = score_and_filter(all_papers, parsed, term_freq)
    
    top_matched = [x[0] for x in scored[:10]]
    
    # LLM replacement for static format
    explanation = explain_trend_llm(keyword, spike_year, top_matched)
            
    return {
        "keyword": keyword,
        "spike_year": spike_year,
        "explanation": explanation
    }

@app.get("/analytics/gap-detection")
def gap_detection(domain: str = Query(...), db: Session = Depends(get_db)):
    parsed = parse_query(domain)
    all_papers = db.query(PaperModel).all()
    term_freq = compute_term_frequencies(all_papers)
    scored = score_and_filter(all_papers, parsed, term_freq)
    
    top_papers = [x[0] for x in scored[:100]]
    gap_sentences = find_gaps(top_papers)
    
    return {
        "domain": domain,
        "gaps": gap_sentences
    }

