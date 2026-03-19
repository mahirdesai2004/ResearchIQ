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
    llm_interpret_query
)

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
    # 🔥 LLM QUERY UNDERSTANDING: interpret raw query before parsing
    interpreted_query = llm_interpret_query(req.topic)
    parsed = parse_query(interpreted_query)
    
    all_papers = db.query(PaperModel).all()
    # GLOBAL FREQUENCY (computed on-demand for simplicity in small datasets)
    term_freq = compute_term_frequencies(all_papers)
    scored = score_and_filter(all_papers, parsed, term_freq)
    
    # Base ranked extraction
    ranked_paper_objects = [p for p, _, _ in scored]
    paper_metadata = {id(p): {"score": s, "matched": m} for p, s, m in scored}
    
    print("\n=== QUERY DEBUG ===")
    print("Raw Query:", req.topic)
    print("Interpreted:", interpreted_query)
    print("Parsed Terms:", parsed)

    for p, score, matched in scored[:10]:
        title_str = p.title or ""
        print("TITLE:", title_str[:80])
        print("MATCHED:", matched)
        print("SCORE:", score)
        print("---")
        
    if len(ranked_paper_objects) == 0:
        return {
            "topic": req.topic, 
            "purpose": req.purpose, 
            "count": 0, 
            "papers": [],
            "summary": "No relevant papers found matching your query."
        }
    
    # 🔥 LLM LAYER
    # Filter only applied to top results (top 20) inside the llm function to avoid massive costs
    filtered = llm_filter_irrelevant(req.topic, ranked_paper_objects)
    
    # Rerank on top of the filtered safe stack
    candidates = filtered if filtered else ranked_paper_objects
    reranked = llm_rerank(req.topic, candidates)
    
    # Merge carefully to avoid duplicating the reranked objects
    final_ranked: List[Any] = list(reranked)
    reranked_ids = {p.id for p in reranked}
    for p in ranked_paper_objects:
        if p.id not in reranked_ids:
            final_ranked.append(p)
    
    # Purpose Logic
    summary_text = None
    if req.purpose == "quick overview":
        final = final_ranked[:5]
        summary_text = quick_summary(req.topic, final)
    elif req.purpose == "deep dive":
        final = final_ranked[:req.num_papers]
    elif req.purpose == "literature review":
        final = diversify(final_ranked, req.num_papers)
        # Note: literature_review_llm returns dict. The frontend currently puts 'summary' and 'open_questions' directly from the /analytics/literature-review endpoint
        # For /research/query, they just ask for 'summary', but we'll return the string version if it asks for string.
        # Actually, literature_review outputs a structured dict. I will serialize it to text or provide it as a dict. 
        # I'll let literature_review_llm be formatted nicely in summary field.
        rev = literature_review_llm(req.topic, final)
        summary_text = rev.get("summary", "Summary not generated.")
        # if frontend expects dict on query page, we will just send it in summary string
        # Actually user prompt: 'summary = literature_review(request.topic, selected)'. so just assign it.
    else:
        final = final_ranked[:req.num_papers]
        
    response_papers = []
    for p in final:
        meta = paper_metadata.get(id(p), {"score": 0, "matched": []})
        
        # 🔥 LLM WHY Badge (Optional integration)
        why = why_this_paper(req.topic, p)
        
        # Only show important matches for display
        matched = meta.get("matched", [])
        matched_display = [t for t in matched if parsed.get(t, 0) >= 5]
        
        kw_list = list(matched_display)
        if why and why != "Relevant based on keywords.":
            kw_list.append(f"LLM insight: {why}")
            
        response_papers.append({
            "title": p.title,
            "year": p.year,
            "authors": p.authors,
            "abstract": p.abstract,
            "matched_keywords": kw_list,
            "score": meta.get("score", 0),
            "id": p.id,
            "llm_reason": why
        })
        
    response_data: dict[str, Any] = {
        "topic": req.topic, 
        "purpose": req.purpose, 
        "count": len(response_papers), 
        "papers": response_papers,
        "summary": summary_text
    }
    
    return response_data

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
            "abstract": p.abstract
        }
        for p in papers
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
