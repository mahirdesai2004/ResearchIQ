from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import logging
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import engine, SessionLocal, Base, PaperModel, get_db
from arxiv_ingest import ingest_by_year
from ranking import rank_papers, normalize_query

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
# Core Fixes and Logic Additions
# -------------------------------------------------------------------
def reset_database():
    db = SessionLocal()
    db.query(PaperModel).delete()
    db.commit()
    db.close()

def search_papers_ranked(db: Session, topic: str, limit: int = 100) -> list:
    normalized = normalize_query(topic)
    all_papers = db.query(PaperModel).all()
    ranked = rank_papers(normalized, all_papers)
    return list(ranked)[:limit]

def diversify_by_year(papers: list, num: int) -> list:
    from collections import defaultdict
    by_year = defaultdict(list)
    
    for p in papers:
        by_year[p.year or 0].append(p)

    years = sorted(by_year.keys(), reverse=True)
    result = []
    i = 0

    while len(result) < num and years:
        year = years[i % len(years)]
        if by_year[year]:
            result.append(by_year[year].pop(0))
        i += 1
        
        # Stop if all buckets are empty
        if all(len(lst) == 0 for lst in by_year.values()):
            break

    return result

def generate_summary(papers: list) -> str:
    abstracts = [p.abstract for p in papers if p.abstract][:5]
    return " ".join(abstracts[:2])[:600]

from collections import Counter
def extract_top_keywords(papers: list) -> List[str]:
    keywords = []
    for p in papers:
        if p.keywords:
            keywords.extend(p.keywords)
    return [k for k, _ in Counter(keywords).most_common(8)]

# -------------------------------------------------------------------
# Auto-seed
# -------------------------------------------------------------------
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

@app.get("/")
def read_root():
    return {"message": "Welcome to ResearchIQ API"}

@app.get("/papers/arxiv")
def get_arxiv_papers(query: str = Query("ai"), max_results: int = Query(50)):
    normalized = normalize_query(query)
    res = ingest_by_year(normalized, start_year=2018, end_year=2026)
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

@app.post("/research/query")
def research_query(req: ResearchQuery, db: Session = Depends(get_db)):
    papers = search_papers_ranked(db, req.topic, limit=100)
    
    if not papers:
        # Fallback to latest papers broadly
        papers = sorted(db.query(PaperModel).all(), key=lambda p: (p.year or 0), reverse=True)[:100]

    safe_papers = list(papers)
    
    if req.purpose == "deep dive":
        final_papers = safe_papers[:req.num_papers]
    elif req.purpose == "quick overview":
        final_papers = safe_papers[:5]
    elif req.purpose == "literature review":
        final_papers = diversify_by_year(safe_papers, req.num_papers)
    else:
        final_papers = safe_papers[:req.num_papers]

    response_data: dict[str, Any] = {
        "topic": req.topic, 
        "purpose": req.purpose, 
        "count": len(final_papers), 
        "papers": final_papers
    }
    
    if req.purpose == "deep dive":
        response_data["related_keywords"] = extract_top_keywords(final_papers)
        
    return response_data

@app.get("/analytics/keyword-trend")
def keyword_trend(keyword: str = Query(...)):
    db = SessionLocal()
    trend = (
        db.query(PaperModel.year, func.count(PaperModel.id))
        .filter(PaperModel.title.ilike(f"%{keyword}%"))
        .group_by(PaperModel.year)
        .order_by(PaperModel.year)
        .all()
    )
    db.close()

    if len(trend) < 3:
        return {"message": "Not enough data"}

    return [{"year": y, "count": c} for y, c in trend]

# -------------------------------------------------------------------
# Tableau Export
# -------------------------------------------------------------------
@app.get("/export/tableau-data")
def export_data():
    db = SessionLocal()
    papers = db.query(PaperModel).all()
    db.close()

    return [
        {
            "title": p.title,
            "year": p.year,
            "domain": ",".join(p.domains) if hasattr(p, 'domains') and p.domains else "",
            "keywords": ",".join(p.keywords) if hasattr(p, 'keywords') and p.keywords else "",
            "authors": ",".join(p.authors) if hasattr(p, 'authors') and p.authors else ""
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

    return [{"year": y, "total_papers": c} for y, c in results]


# -------------------------------------------------------------------
# Intelligence Features
# -------------------------------------------------------------------
@app.get("/analytics/literature-review")
def literature_review(domain: str = Query(...), db: Session = Depends(get_db)):
    papers = search_papers_ranked(db, domain, limit=100)
    if not papers:
        papers = list(db.query(PaperModel).all())[:100]

    top_papers = list(papers[:50])
    
    current_year = datetime.now().year
    older_papers = [p for p in top_papers if (p.year or 0) < current_year - 2]
    recent_papers = [p for p in top_papers if (p.year or 0) >= current_year - 2]
    
    summary = generate_summary(top_papers)
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
        "top_papers": top_papers[:10]
    }

@app.get("/analytics/trend-explanation")
def trend_explanation(keyword: str = Query(...), db: Session = Depends(get_db)):
    trend_data = keyword_trend(keyword)
    if isinstance(trend_data, dict) and "message" in trend_data:
        return {"keyword": keyword, "spike_year": None, "explanation": "Not enough data to explain trend for this topic."}
         
    # Find spike year
    spike_year = max(trend_data, key=lambda d: d["count"])["year"]
    
    all_papers = db.query(PaperModel).filter(PaperModel.year == spike_year).all()
    ranked = search_papers_ranked(db, keyword, limit=100)
    explanation = f"In {spike_year}, research interest peaked. "
    if ranked:
        top_kws = extract_top_keywords(list(ranked)[:10])
        if top_kws:
            explanation += f"Major breakthroughs frequently discussed {', '.join(top_kws[:3])}. "
            
    return {
        "keyword": keyword,
        "spike_year": spike_year,
        "explanation": explanation
    }

@app.get("/analytics/gap-detection")
def gap_detection(domain: str = Query(...), db: Session = Depends(get_db)):
    papers = search_papers_ranked(db, domain, limit=100)
    top_papers = list(papers[:100])
    
    all_kws = []
    for p in top_papers:
        if p.keywords:
            all_kws.extend([k.lower() for k in p.keywords if len(k) > 3])
            
    counts = Counter(all_kws)
    sorted_kws = counts.most_common()
    if len(sorted_kws) > 20:
        tail = [(kw, count) for kw, count in sorted_kws if count > 1]
        gaps = tail[-10:] if tail else sorted_kws[-10:]
    else:
        gaps = sorted_kws[-5:]
        
    return {
        "domain": domain,
        "gaps": [{"keyword": kw, "count": dict(counts).get(kw, 1)} for kw, _ in gaps]
    }

@app.get("/system/stats")
def get_system_stats(db: Session = Depends(get_db)):
    papers = db.query(PaperModel).all()
    total = len(papers)
    domains_count: Dict[str, int] = {}
    years_count: Dict[int, int] = {}

    for p in papers:
        for d in (p.domains or []):
            domains_count[d] = domains_count.get(d, 0) + 1
        if p.year is not None:
            years_count[p.year] = years_count.get(p.year, 0) + 1

    return {
        "total_papers": total,
        "papers_per_domain": domains_count,
        "year_distribution": years_count
    }
