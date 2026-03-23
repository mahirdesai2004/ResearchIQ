# pyre-ignore-all-errors
from fastapi import FastAPI, Query, HTTPException, Depends # pyre-ignore
from fastapi.responses import StreamingResponse # pyre-ignore
from fastapi.middleware.cors import CORSMiddleware # pyre-ignore
from sqlalchemy.orm import Session # pyre-ignore
from sqlalchemy import func # pyre-ignore
from pydantic import BaseModel # pyre-ignore
import logging
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
    paper_summary,
    paper_explain,
    paper_flowchart,
    generate_gap_sentences,
    generate_field_flow
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
# Auto-seed
# -------------------------------------------------------------------
def reset_database():
    db = SessionLocal()
    db.query(PaperModel).delete()
    db.commit()
    db.close()

def _auto_seed():
    try:
        db = SessionLocal()
        count = db.query(func.count(PaperModel.id)).scalar() or 0
        db.close()

        if count < 100:
            logging.info("Auto-seed: DB has too few papers. Resetting and batch ingesting over multiple years...")
            reset_database()
            seed_topics = ["artificial intelligence", "machine learning", "natural language processing", "computer vision"]
            for topic in seed_topics:
                try:
                    ingest_by_year(topic, start_year=2018, end_year=2026)
                except Exception as e:
                    logging.warning(f"Auto-seed failed for '{topic}': {e}")
            logging.info("Auto-seed complete.")
    except Exception as e:
        logging.error(f"Auto-seed error: {e}")

threading.Thread(target=_auto_seed, daemon=True).start()

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

@app.post("/papers/arxiv/batch")
def trigger_batch_ingestion():
    reset_database()
    domains = ["artificial intelligence", "machine learning", "natural language processing", "computer vision"]
    results_list = []
    for d in domains:
        res = ingest_by_year(d, 2018, 2026)
        results_list.append(res)
    return {"message": "Batch ingestion completed", "results": results_list}


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
    all_papers = db.query(PaperModel).all()
    
    # 2. Strict Filtering
    candidates = strict_filter(all_papers, parsed)
    
    if not candidates:
        print("⚠️ FILTER TOO STRICT → FALLBACK TRIGGERED")
        candidates = all_papers[:20]

    print("QUERY:", req.topic)
    print("PARSED:", parsed)
    print("TOTAL PAPERS:", len(all_papers))
    print("AFTER FILTER:", len(candidates))
    
    if len(candidates) == 0:
        return {
            "topic": req.topic, 
            "purpose": req.purpose, 
            "count": 0, 
            "papers": [],
            "summary": "No relevant papers found matching your strict criteria.",
            "status": "complete"
        }
        
    # 3. FAISS Semantic Search
    index, _ = build_index(candidates)
    semantic_results = semantic_search(req.topic, candidates, index)
    
    # 4. LLM Reranking
    final_ranked = llm_rerank(req.topic, semantic_results)
    
    print("=== FINAL PAPERS ===", [p.title for p in final_ranked])

    # Build response papers
    response_papers = []
    core_terms = parsed.get("core_terms", [])
    context_terms = parsed.get("context_terms", [])
    all_search_terms = core_terms + context_terms
    
    for p in final_ranked[:req.num_papers]:
        # Compute confidence score
        text = ((p.title or "") + " " + (p.abstract or "")).lower()
        core_matches = sum(1 for t in core_terms if t in text)
        context_matches = sum(1 for t in context_terms if t in text)
        total_terms = len(all_search_terms) if all_search_terms else 1
        confidence = int(((core_matches + context_matches) / total_terms) * 100)
        
        # Collect ALL matched terms (core + context)
        matched_keywords = [t for t in all_search_terms if t in text]
        
        # Build intelligent reason
        reasons = []
        if core_matches > 0:
            reasons.append(f"Core: {', '.join([t for t in core_terms if t in text])}")
        if context_matches > 0:
            reasons.append(f"Context: {', '.join([t for t in context_terms if t in text])}")
        llm_reason = " | ".join(reasons) if reasons else "Semantic match via FAISS"
        
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

    for p in papers:
        if not p.year:
            continue

        text = f"{p.title or ''} {p.abstract or ''}".lower()
        if keyword.lower() in text:
            data[p.year] += 1
            
    db.close()

    if len(data) < 3:
        return {"message": "Not enough data"}

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
    gaps = find_gaps(top_papers)
    
    from collections import Counter
    all_kws = []
    for p in top_papers:
        if p.keywords:
            all_kws.extend([str(k).lower() for k in p.keywords if len(str(k)) > 3])
    counts = Counter(all_kws)
        
    return {
        "domain": domain,
        "gaps": [{"keyword": kw, "count": counts.get(kw, 1)} for kw in gaps]
    }
