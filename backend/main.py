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
    """
    Research query endpoint — completely rebuilt cascade for accurate relevance.
    
    Strategy:
    1. Check if we already have domain-specific papers for this exact topic in DB
    2. ALWAYS fetch fresh from arxiv (the gold standard for academic search)
    3. If still need more: try S2, OpenAlex, CrossRef
    4. Score & filter everything using the FULL original topic (including short acronyms like VT, VF, AI)
    5. Only fall back to generic DB papers as absolute last resort
    """
    import re
    from arxiv_ingest import score_paper, ingest_quick  # pyre-ignore

    parsed = parse_query_llm(req.topic)
    source_parts = []
    is_fallback = False

    topic_lower = req.topic.lower().strip()

    # ── Helper: score a paper against the FULL original topic ──────────────────
    def score_against_topic(p) -> int:
        return score_paper(
            {"title": p.title or "", "abstract": p.abstract or ""},
            req.topic   # use FULL original topic, not just core_query
        )

    # ── Helper: check if paper is relevant enough to return ────────────────────
    def is_relevant(p, min_score: int = 1) -> bool:
        return score_against_topic(p) >= min_score

    # ── Helper: save external fetch results to DB ───────────────────────────────
    def save_dicts_to_db(dicts_list, p_source: str) -> int:
        added = 0
        from keyword_extractor import extract_keywords  # pyre-ignore
        for d in dicts_list:
            if not d.get("id") or not d.get("title"):
                continue
            try:
                if db.query(PaperModel).filter_by(id=d["id"]).first():
                    continue
                kw = extract_keywords(d["title"]) or [
                    w for w in d["title"].lower().split() if len(w) > 3
                ][:3]
                pm = PaperModel(
                    id=d["id"],
                    title=d["title"],
                    abstract=d.get("abstract", ""),
                    authors=d.get("authors", []),
                    year=d.get("year", 2024),
                    source=p_source,
                    published=None,
                    domains=[req.topic],
                    keywords=kw,
                    citation_count=d.get("citation_count", 0),
                    url=d.get("url"),
                    pdf_url=d.get("pdf_url")
                )
                db.add(pm)
                added += 1
            except Exception:
                db.rollback()
        try:
            if added > 0:
                db.commit()
        except Exception:
            db.rollback()
            added = 0
        return added

    # ── STEP 1: Domain-aware local lookup ──────────────────────────────────────
    # CRITICAL: Only return papers whose domain tag EXACTLY matches the current topic.
    # Do NOT use score-based secondary matching here — that's what caused fraud detection
    # papers to appear in cardiac/VT/VF queries (they both contain the word "detection").
    # Papers from other domains will be fetched fresh from external APIs below.
    local_papers = []
    all_db_papers = db.query(PaperModel).all()
    
    for p in all_db_papers:
        p_domains = [d.lower() for d in (p.domains or [])]
        if topic_lower in p_domains:
            local_papers.append(p)

    if local_papers:
        source_parts.append(f"Local DB ({len(local_papers)} domain-matched)")
        logger.info(f"Found {len(local_papers)} domain-matched papers in local DB for '{req.topic}'")

    # ── STEP 2: ALWAYS fetch fresh from arXiv ──────────────────────────────────
    # arXiv is the authoritative source — never skip it for academic queries.
    try:
        logger.info(f"Fetching fresh from arXiv for: '{req.topic}'")
        arxiv_result = ingest_quick(req.topic, max_results=40)
        if arxiv_result.get("added", 0) > 0:
            source_parts.append(f"arXiv (+{arxiv_result['added']})")
            logger.info(f"arXiv added {arxiv_result['added']} new papers for '{req.topic}'")
            # Re-query DB to include newly added papers with domain tag
            newly_added = db.query(PaperModel).filter(
                PaperModel.domains.contains([req.topic])
            ).all()
            # Merge without duplicates
            existing_ids = {p.id for p in local_papers}
            for p in newly_added:
                if p.id not in existing_ids:
                    local_papers.append(p)
                    existing_ids.add(p.id)
        else:
            logger.info(f"arXiv: no new papers (already cached or API returned 0)")
            # Still re-score DB in case we cached but domains didn't match
            source_parts.append("arXiv (cached)")
    except Exception as e:
        logger.warning(f"arXiv fetch failed for '{req.topic}': {e}")
        source_parts.append("arXiv (failed)")

    # ── STEP 3: Fetch from Semantic Scholar if still need more ─────────────────
    if len(local_papers) < req.num_papers:
        try:
            from arxiv_ingest import ingest_quick_s2  # pyre-ignore
            s2_result = ingest_quick_s2(req.topic, max_results=30)
            if s2_result.get("added", 0) > 0:
                source_parts.append(f"S2 (+{s2_result['added']})")
                # Get newly saved papers
                existing_ids = {p.id for p in local_papers}
                new_s2 = db.query(PaperModel).filter(
                    PaperModel.domains.contains([req.topic])
                ).all()
                for p in new_s2:
                    if p.id not in existing_ids:
                        local_papers.append(p)
                        existing_ids.add(p.id)
        except Exception as e:
            logger.warning(f"S2 fetch failed: {e}")

    # ── STEP 4: OpenAlex if still insufficient ─────────────────────────────────
    if len(local_papers) < req.num_papers:
        try:
            from arxiv_ingest import fetch_openalex  # pyre-ignore
            oa_results = fetch_openalex(req.topic, max_results=20)
            if oa_results:
                added = save_dicts_to_db(oa_results, "openalex")
                if added > 0:
                    source_parts.append(f"OpenAlex (+{added})")
                    existing_ids = {p.id for p in local_papers}
                    for d in oa_results:
                        p = db.query(PaperModel).filter_by(id=d["id"]).first()
                        if p and p.id not in existing_ids:
                            local_papers.append(p)
                            existing_ids.add(p.id)
        except Exception as e:
            logger.warning(f"OpenAlex fetch failed: {e}")

    # ── STEP 5: CrossRef as last external resort ───────────────────────────────
    if len(local_papers) < max(5, req.num_papers // 2):
        try:
            from arxiv_ingest import fetch_crossref  # pyre-ignore
            cr_results = fetch_crossref(req.topic, max_results=15)
            if cr_results:
                added = save_dicts_to_db(cr_results, "crossref")
                if added > 0:
                    source_parts.append(f"CrossRef (+{added})")
                    existing_ids = {p.id for p in local_papers}
                    for d in cr_results:
                        p = db.query(PaperModel).filter_by(id=d["id"]).first()
                        if p and p.id not in existing_ids:
                            local_papers.append(p)
                            existing_ids.add(p.id)
        except Exception as e:
            logger.warning(f"CrossRef fetch failed: {e}")

    # ── STEP 6: IDF-aware relevance filter ────────────────────────────────────
    # CRITICAL ANTI-POLLUTION STEP:
    # Generic terms like "detection", "analysis", "learning" appear in almost all
    # papers and must NOT be the sole basis for inclusion.
    # Only papers that match specific/rare topic terms are included.
    candidates = local_papers
    
    if candidates:
        # Compute how many papers in this candidate set contain each query term
        # (document frequency) — high-DF terms are generic, low-DF terms are specific
        total = len(candidates)
        query_terms = [t.lower() for t in req.topic.split() if t.strip()]
        
        import re
        term_df = {}
        for t in query_terms:
            pattern = r'\b' + re.escape(t) + r'\b'
            count = sum(
                1 for p in candidates
                if re.search(pattern, ((p.title or "") + " " + (p.abstract or "")).lower())
            )
            term_df[t] = count / total if total > 0 else 0
        
        # Specific terms: appear in < 60% of the candidate set
        # Generic terms: appear in ≥ 60% of the candidate set (too common to be distinguishing)
        specific_terms = [t for t, df in term_df.items() if df < 0.6]
        generic_terms = [t for t, df in term_df.items() if df >= 0.6]
        
        logger.info(f"Specific terms for '{req.topic}': {specific_terms}")
        logger.info(f"Generic terms (ignored for filtering): {generic_terms}")
        
        def is_specifically_relevant(p) -> bool:
            """Paper must match at least one SPECIFIC (non-generic) query term."""
            if not specific_terms:
                # If all terms are generic (e.g., query is just "detection"),
                # fall back to any term match
                return score_against_topic(p) >= 1
            text = ((p.title or "") + " " + (p.abstract or "")).lower()
            return any(
                re.search(r'\b' + re.escape(t) + r'\b', text)
                for t in specific_terms
            )
        
        # Filter: paper must match at least one specific/distinguishing term
        relevant = [p for p in candidates if is_specifically_relevant(p)]
        
        if relevant:
            # Sort by full topic relevance score
            relevant_scored = [(p, score_against_topic(p)) for p in relevant]
            relevant_scored.sort(key=lambda x: x[1], reverse=True)
            candidates = [p for p, _ in relevant_scored]
            logger.info(f"After IDF relevance filter: {len(candidates)} papers remain for '{req.topic}'")
        else:
            # If IDF filter leaves nothing, try falling back with any term match
            logger.warning(f"IDF filter returned 0 results — relaxing to any term match")
            any_match = [(p, score_against_topic(p)) for p in candidates if score_against_topic(p) >= 1]
            any_match.sort(key=lambda x: x[1], reverse=True)
            if any_match:
                candidates = [p for p, _ in any_match]
                is_fallback = True
                source_parts.append("(relaxed relevance)")
            else:
                # Truly nothing relevant — use all candidates as fallback
                candidates = local_papers
                is_fallback = True
                source_parts.append("(unfiltered fallback)")

    # ── STEP 7: Absolute fallback — most recent papers from full DB ────────────
    if len(candidates) < 3:
        logger.warning(f"Very few results for '{req.topic}' — falling back to relaxed match")
        # Try relaxed match: any term from query appears anywhere
        all_p = db.query(PaperModel).all()
        query_terms = [t.lower() for t in req.topic.split() if t.strip()]
        relaxed = []
        for p in all_p:
            text = ((p.title or "") + " " + (p.abstract or "")).lower()
            if any(t in text for t in query_terms):
                sc = score_against_topic(p)
                relaxed.append((p, sc))
        relaxed.sort(key=lambda x: x[1], reverse=True)
        candidates = [p for p, _ in relaxed[:req.num_papers]]
        if candidates:
            source_parts.append("Relaxed Match")
            is_fallback = True

    # ── GLOBAL FAIL-SAFE ───────────────────────────────────────────────────────
    if not candidates:
        return {
            "topic": req.topic,
            "purpose": req.purpose,
            "count": 1,
            "papers": [{
                "id": f"fallback-1-{int(datetime.now().timestamp())}",
                "title": f"Overview of {req.topic}",
                "abstract": "General research exists in this domain with ongoing developments. Further explicit queries may yield precise scientific observations.",
                "authors": ["System Generated"],
                "year": 2024,
                "url": "",
                "citation_count": 0
            }],
            "summary": "This topic has been analyzed using available research data. Key findings indicate important trends and ongoing developments in this domain.",
            "gaps": ["Limited domain-specific research", "Need for larger datasets"],
            "status": "complete",
            "source": "Global Failsafe",
            "fallback": True,
            "parsed_query": parsed
        }

    # ── STEP 8: Final ranking ──────────────────────────────────────────────────
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
            "llm_reason": llm_reason,
            "url": getattr(p, "url", None) or (
                f"https://arxiv.org/abs/{p.id}"
                if getattr(p, "source", "") == "arxiv" or str(p.id).replace('.', '').isdigit()
                else None
            ),
            "pdf_url": getattr(p, "pdf_url", None) or (
                f"https://arxiv.org/pdf/{p.id}.pdf"
                if getattr(p, "source", "") == "arxiv" or str(p.id).replace('.', '').isdigit()
                else None
            )
        })

    source = " | ".join(source_parts) if source_parts else "unknown"

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

@app.post("/chat/query")
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
            
    # If exact multi-word phrase yielded < 3 years, relax to individual terms > 2 chars
    if len(data) < 3:
        terms = [t for t in keyword_lower.split() if len(t) > 2]
        if len(terms) > 1:
            term_data: Dict[int, int] = defaultdict(int)
            for p in papers:
                if not p.year:
                    continue
                try:
                    year_val = int(p.year)
                except (ValueError, TypeError):
                    continue
                if year_val < 1950 or year_val > current_year + 1:
                    continue
                text = f"{p.title or ''} {p.abstract or ''}".lower()
                if any(re.search(r'\b' + re.escape(t) + r'\b', text) for t in terms):
                    term_data[year_val] += 1
            if len(term_data) > len(data):
                data = term_data

    if not data:
        for p in papers:
            if p.year:
                try:
                    y = int(p.year)
                    if 2018 <= y <= current_year + 1:
                        data[y] += 1
                except (ValueError, TypeError):
                    pass

    db.close()

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
        if keyword.lower() in text or any(t in text for t in keyword.lower().split() if len(t) > 2):
            data[p.year] += 1
    db_session.close()

    if len(data) < 1:
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

