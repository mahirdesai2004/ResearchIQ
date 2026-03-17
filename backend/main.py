from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import logging
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from collections import defaultdict

from database import engine, SessionLocal, Base, PaperModel, get_db
from arxiv_ingest import ingest_by_year
from ranking import filter_and_score
from query_parser import parse_query
from analytics import find_gaps

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
    parsed = parse_query(query)
    res = ingest_by_year(parsed["normalized"], start_year=2018, end_year=2026)
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
    parsed = parse_query(req.topic)
    
    all_papers = db.query(PaperModel).all()
    scored = filter_and_score(all_papers, parsed)
    
    # scored is list of tuples: (paper, score, matched)
    ranked_paper_objects = [x[0] for x in scored]
    
    if req.purpose == "quick overview":
        final = ranked_paper_objects[:5]
    elif req.purpose == "deep dive":
        final = ranked_paper_objects[:req.num_papers]
    elif req.purpose == "literature review":
        final = diversify(ranked_paper_objects, req.num_papers)
    else:
        final = ranked_paper_objects[:req.num_papers]
        
    paper_metadata = {id(p): {"score": s, "matched": m} for p, s, m in scored}
    
    response_papers = []
    for p in final:
        meta = paper_metadata.get(id(p), {"score": 0, "matched": []})
        response_papers.append({
            "title": p.title,
            "year": p.year,
            "authors": p.authors,
            "abstract": p.abstract,
            "matched_keywords": meta["matched"],
            "score": meta["score"],
            "id": p.id
        })
        
    response_data: dict[str, Any] = {
        "topic": req.topic, 
        "purpose": req.purpose, 
        "count": len(response_papers), 
        "papers": response_papers
    }
    
    return response_data

@app.get("/analytics/keyword-trend")
def keyword_trend(keyword: str):
    db: Session = SessionLocal()
    data = defaultdict(int)

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
    scored = filter_and_score(all_papers, parsed)
    
    top_papers = [x[0] for x in scored[:50]]
    if not top_papers:
        top_papers = list(all_papers[:50])
    
    current_year = datetime.now().year
    older_papers = [p for p in top_papers if (p.year or 0) < current_year - 2]
    recent_papers = [p for p in top_papers if (p.year or 0) >= current_year - 2]
    
    abstracts = [p.abstract for p in top_papers if p.abstract][:5]
    summary = " ".join(abstracts[:2])[:600]
    if not summary:
        summary = "No detailed abstracts available to summarize."
        
    import re
    open_questions = []
    question_keywords = ["future", "challenge", "limit", "remain", "open problem"]
    for p in recent_papers[:10]:
        if not p.abstract: continue
        sentences = re.split(r'(?<=[.!?]) +', p.abstract)
        for s in sentences:
            if any(qk in s.lower() for qk in question_keywords):
                open_questions.append(s)
                if len(open_questions) >= 5:
                    break
        if len(open_questions) >= 5:
            break
            
    if not open_questions:
        open_questions = ["Requires further investigation into real-world scalability.", "Current methods face limitations in diverse environments."]
        
    return {
        "summary": summary,
        "key_themes": extract_top_keywords(top_papers),
        "recent_trends": extract_top_keywords(recent_papers),
        "open_questions": open_questions,
        "top_papers": [{"title": p.title, "year": p.year} for p in top_papers[:10]]
    }

@app.get("/analytics/trend-explanation")
def trend_explanation(keyword: str = Query(...), db: Session = Depends(get_db)):
    db_session: Session = SessionLocal()
    data = defaultdict(int)

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
         
    spike_year = max(data.keys(), key=lambda y: data[y])
    
    parsed = parse_query(keyword)
    all_papers = db.query(PaperModel).filter(PaperModel.year == spike_year).all()
    scored = filter_and_score(all_papers, parsed)
    
    explanation = f"In {spike_year}, research interest peaked. "
    if scored:
        top_kws = extract_top_keywords([x[0] for x in scored[:10]])
        if top_kws:
            explanation += f"Major breakthroughs frequently discussed {', '.join(top_kws[:3])}. "
            
    return {
        "keyword": keyword,
        "spike_year": spike_year,
        "explanation": explanation
    }

@app.get("/analytics/gap-detection")
def gap_detection(domain: str = Query(...), db: Session = Depends(get_db)):
    parsed = parse_query(domain)
    all_papers = db.query(PaperModel).all()
    scored = filter_and_score(all_papers, parsed)
    
    top_papers = [x[0] for x in scored[:100]]
    gaps = find_gaps(top_papers)
    
    from collections import Counter
    all_kws = []
    for p in top_papers:
        if p.keywords:
            all_kws.extend([k.lower() for k in p.keywords if len(k) > 3])
    counts = Counter(all_kws)
        
    return {
        "domain": domain,
        "gaps": [{"keyword": kw, "count": counts.get(kw, 1)} for kw in gaps]
    }
