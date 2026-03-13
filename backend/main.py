from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import csv
import io
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import engine, SessionLocal, Base, PaperModel, get_db
from arxiv_ingest import ingest_papers_from_arxiv
from ranking import rank_papers
from purpose_handlers import diversify_by_year, extract_related_keywords
from utils import logger, summarize_abstract

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
# In-memory cache to avoid repeated arXiv fetches for the same topic
# -------------------------------------------------------------------
fetch_cache: Dict[str, datetime] = {}

# -------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------
@app.get("/health")
def health_check():
    return {"status": "ok"}

@app.get("/")
def read_root():
    return {"message": "Welcome to ResearchIQ API"}

# -------------------------------------------------------------------
# GET /papers/arxiv – Fetch and ingest papers from arXiv
# -------------------------------------------------------------------
@app.get("/papers/arxiv")
def get_arxiv_papers(
    query: str = Query("ai", description="Search query for arXiv"),
    max_results: int = Query(50, description="Number of results to fetch"),
):
    logger.info(f"GET /papers/arxiv – query='{query}', max_results={max_results}")
    try:
        result = ingest_papers_from_arxiv(query, max_results=max_results)
        fetch_cache[query.lower()] = datetime.now()
        logger.info(f"GET /papers/arxiv – fetched={result['fetched']}, added={result['added']}")
        return {
            "query": query,
            "fetched": result["fetched"],
            "added": result["added"],
            "message": f"Added {result['added']} new papers"
        }
    except Exception as e:
        logger.error(f"GET /papers/arxiv failed: {e}")
        raise HTTPException(status_code=503, detail=f"arXiv fetch failed: {str(e)}")

# -------------------------------------------------------------------
# POST /papers/arxiv/batch – Batch ingest for predefined domains
# -------------------------------------------------------------------
@app.post("/papers/arxiv/batch")
def trigger_batch_ingestion():
    domains = ["AI", "ML", "NLP", "LLM", "CV"]
    logger.info("POST /papers/arxiv/batch – starting batch ingestion")

    results_list: List[Dict[str, Any]] = []
    for d in domains:
        try:
            res = ingest_papers_from_arxiv(d, max_results=50)
            fetch_cache[d.lower()] = datetime.now()
            results_list.append(res)
            logger.info(f"  Batch '{d}': fetched={res['fetched']}, added={res['added']}")
        except Exception as e:
            logger.error(f"  Batch '{d}' failed: {e}")
            results_list.append({"topic": d, "fetched": 0, "added": 0, "error": str(e)})

    return {
        "message": "Batch ingestion completed",
        "results": results_list
    }

# -------------------------------------------------------------------
# POST /research/query – Context-aware research query
# -------------------------------------------------------------------
@app.post("/research/query")
def research_query(req: ResearchQuery, db: Session = Depends(get_db)):
    topic_lower = req.topic.lower()
    logger.info(f"POST /research/query – topic='{req.topic}', purpose='{req.purpose}', num_papers={req.num_papers}")

    # Find relevant papers using ILIKE-style matching on title OR abstract
    all_papers = db.query(PaperModel).all()
    relevant_papers: List[Any] = []

    for p in all_papers:
        title = (p.title or "").lower()
        abstract = (p.abstract or "").lower()
        if topic_lower in title or topic_lower in abstract:
            relevant_papers.append(p)

    local_count = len(relevant_papers)
    logger.info(f"  Local matches: {local_count}")

    # Fetch from arXiv if not enough and not fetched recently
    current_time = datetime.now()
    last_fetch: Optional[datetime] = fetch_cache.get(topic_lower)
    should_fetch = local_count < req.num_papers and (
        last_fetch is None or (current_time - last_fetch).total_seconds() > 3600
    )

    if should_fetch:
        logger.info(f"  Fetching from arXiv for '{req.topic}'")
        max_res = max(100, req.num_papers * 2)
        try:
            ingest_papers_from_arxiv(req.topic, max_results=max_res)
            fetch_cache[topic_lower] = datetime.now()

            # Re-query after ingestion
            all_papers = db.query(PaperModel).all()
            relevant_papers = []
            for p in all_papers:
                title = (p.title or "").lower()
                abstract = (p.abstract or "").lower()
                if topic_lower in title or topic_lower in abstract:
                    relevant_papers.append(p)
            logger.info(f"  After fetch, local matches: {len(relevant_papers)}")
        except Exception as e:
            logger.error(f"  arXiv fetch failed: {e}")

    # Rank all relevant papers
    ranked_papers = rank_papers(req.topic, relevant_papers)

    # Apply purpose-aware logic
    purpose_lower = req.purpose.lower()
    response_data: Dict[str, Any] = {"topic": req.topic, "purpose": req.purpose}

    safe_ranked: List[Any] = list(ranked_papers) if ranked_papers else []

    if purpose_lower == "literature review":
        final_papers = diversify_by_year(safe_ranked, req.num_papers)
    elif purpose_lower == "quick overview":
        final_papers = safe_ranked[:5]
        for p in final_papers:
            if not p.summary:
                p.summary = summarize_abstract(p.abstract or "")
                db.commit()
    elif purpose_lower == "deep dive":
        final_papers = safe_ranked[:req.num_papers]
        top_keywords = extract_related_keywords(final_papers)
        response_data["related_keywords"] = top_keywords
    else:
        final_papers = safe_ranked[:req.num_papers]

    response_data["count"] = len(final_papers)
    response_data["papers"] = final_papers

    logger.info(f"  Returning {len(final_papers)} papers")
    return response_data

# -------------------------------------------------------------------
# GET /analytics/filter – Filter stored papers
# -------------------------------------------------------------------
@app.get("/analytics/filter")
def filter_papers(
    q: Optional[str] = Query(None, description="Search query for full-text filtering"),
    year_min: Optional[int] = Query(None),
    year_max: Optional[int] = Query(None),
    domains: Optional[str] = Query(None, description="Comma-separated domains"),
    keyword: Optional[str] = Query(None, description="Keyword filter (legacy support)"),
    limit: int = Query(20),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    logger.info(f"GET /analytics/filter – q={q}, keyword={keyword}, year_min={year_min}, year_max={year_max}")
    query = db.query(PaperModel)

    if year_min:
        query = query.filter(PaperModel.year >= year_min)
    if year_max:
        query = query.filter(PaperModel.year <= year_max)

    papers = query.all()

    # Filter by domain
    if domains:
        domain_list = [d.strip().lower() for d in domains.split(",") if d.strip()]
        papers = [
            p for p in papers
            if any(d in [x.lower() for x in (p.domains or [])] for d in domain_list)
        ]

    # Full-text search: support both 'q' and legacy 'keyword' param
    search_term = q or keyword
    if search_term:
        papers = rank_papers(search_term, papers)

    paper_list: List[Any] = list(papers) if papers else []
    paginated = paper_list[offset:offset + limit]

    logger.info(f"  Found {len(paper_list)} papers, returning {len(paginated)}")
    return {
        "count": len(paper_list),
        "returned": len(paginated),
        "papers": paginated
    }

# -------------------------------------------------------------------
# GET /analytics/yearly-count
# -------------------------------------------------------------------
@app.get("/analytics/yearly-count")
def get_yearly_count(domain: Optional[str] = None, db: Session = Depends(get_db)):
    papers = db.query(PaperModel).all()
    yearly_counts: Dict[int, int] = {}

    for p in papers:
        if domain:
            p_domains = [d.lower() for d in (p.domains or [])]
            if domain.lower() not in p_domains:
                continue
        y = p.year
        if y is not None:
            yearly_counts[y] = yearly_counts.get(y, 0) + 1

    return {"domain": domain or "all", "yearly_counts": yearly_counts}

# -------------------------------------------------------------------
# GET /analytics/keyword-trend
# -------------------------------------------------------------------
@app.get("/analytics/keyword-trend")
def get_keyword_trend(keyword: str = Query(...), db: Session = Depends(get_db)):
    kw = keyword.lower()
    papers = db.query(PaperModel).all()
    yearly_counts: Dict[int, int] = {}

    for p in papers:
        kw_list = [k.lower() for k in (p.keywords or [])]
        title = (p.title or "").lower()
        abstract = (p.abstract or "").lower()
        if kw in kw_list or kw in title or kw in abstract:
            y = p.year
            if y is not None:
                yearly_counts[y] = yearly_counts.get(y, 0) + 1

    return {"keyword": keyword, "yearly_counts": yearly_counts}

# -------------------------------------------------------------------
# GET /export/tableau-data – CSV streaming export
# -------------------------------------------------------------------
@app.get("/export/tableau-data")
def export_tableau_data(
    domain: Optional[str] = None,
    year_min: Optional[int] = None,
    year_max: Optional[int] = None,
    db: Session = Depends(get_db)
):
    query = db.query(PaperModel)
    if year_min:
        query = query.filter(PaperModel.year >= year_min)
    if year_max:
        query = query.filter(PaperModel.year <= year_max)

    papers = query.all()

    def generate_csv():
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["title", "year", "domain", "keywords"])
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)

        for p in papers:
            if domain and domain.lower() not in [d.lower() for d in (p.domains or [])]:
                continue
            p_domain = (p.domains or ["Unknown"])[0]
            keywords_str = ",".join(p.keywords or [])
            writer.writerow([p.title, p.year, p_domain, keywords_str])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tableau_export.csv"}
    )

# -------------------------------------------------------------------
# GET /system/stats – System statistics
# -------------------------------------------------------------------
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
