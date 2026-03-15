from fastapi import FastAPI, Query, HTTPException, Depends
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import csv
import io
import logging
import threading
from datetime import datetime
from typing import List, Optional, Dict, Any

from database import engine, SessionLocal, Base, PaperModel, get_db
from arxiv_ingest import ingest_papers_from_arxiv
from ranking import rank_papers, normalize_query, get_query_variants
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
# In-memory cache to avoid repeated arXiv fetches (1 hour TTL)
# -------------------------------------------------------------------
fetch_cache: Dict[str, datetime] = {}

def _is_cache_valid(key: str) -> bool:
    last = fetch_cache.get(key)
    if last is None:
        return False
    return (datetime.now() - last).total_seconds() < 3600

# -------------------------------------------------------------------
# Auto-seed: ensure DB has enough papers on startup
# -------------------------------------------------------------------
def _auto_seed():
    """If DB has fewer than 100 papers, trigger batch ingestion in background."""
    try:
        db = SessionLocal()
        count = db.query(func.count(PaperModel.id)).scalar() or 0
        db.close()

        if count < 100:
            logger.info(f"Auto-seed: DB has only {count} papers. Triggering batch ingestion...")
            seed_topics = [
                "artificial intelligence",
                "machine learning",
                "natural language processing",
                "computer vision",
            ]
            for topic in seed_topics:
                try:
                    ingest_papers_from_arxiv(topic, max_results=50)
                    fetch_cache[topic] = datetime.now()
                except Exception as e:
                    logger.warning(f"Auto-seed failed for '{topic}': {e}")
            logger.info("Auto-seed complete.")
        else:
            logger.info(f"Auto-seed: DB has {count} papers. No seeding needed.")
    except Exception as e:
        logger.error(f"Auto-seed error: {e}")

# Run auto-seed in background thread so startup isn't blocked
threading.Thread(target=_auto_seed, daemon=True).start()

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
# GET /papers/arxiv
# -------------------------------------------------------------------
@app.get("/papers/arxiv")
def get_arxiv_papers(
    query: str = Query("ai", description="Search query for arXiv"),
    max_results: int = Query(50, description="Number of results to fetch"),
):
    normalized = normalize_query(query)
    logger.info(f"GET /papers/arxiv – query='{query}' (normalized='{normalized}'), max_results={max_results}")

    if _is_cache_valid(normalized):
        logger.info(f"  Skipping fetch – cached within last hour")
        return {"query": query, "fetched": 0, "added": 0, "message": "Recently fetched, using cache"}

    try:
        result = ingest_papers_from_arxiv(normalized, max_results=max_results)
        fetch_cache[normalized] = datetime.now()
        logger.info(f"  fetched={result['fetched']}, added={result['added']}")
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
# POST /papers/arxiv/batch
# -------------------------------------------------------------------
@app.post("/papers/arxiv/batch")
def trigger_batch_ingestion():
    domains = [
        "artificial intelligence",
        "machine learning",
        "natural language processing",
        "large language model",
        "computer vision",
    ]
    logger.info("POST /papers/arxiv/batch – starting batch ingestion")

    results_list: List[Dict[str, Any]] = []
    for d in domains:
        if _is_cache_valid(d):
            results_list.append({"topic": d, "fetched": 0, "added": 0, "skipped": "cached"})
            continue
        try:
            res = ingest_papers_from_arxiv(d, max_results=50)
            fetch_cache[d] = datetime.now()
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
    normalized = normalize_query(req.topic)
    logger.info(f"POST /research/query – topic='{req.topic}' (normalized='{normalized}'), purpose='{req.purpose}', num_papers={req.num_papers}")

    # Fetch ALL papers from DB, rank in Python (broad set, no strict SQL filters)
    all_papers = db.query(PaperModel).all()
    total_in_db = len(all_papers)
    logger.info(f"  Total papers in DB: {total_in_db}")

    # Rank using soft matching with synonym expansion
    ranked = rank_papers(normalized, all_papers)
    local_count = len(ranked)
    logger.info(f"  Relevant matches after ranking: {local_count}")

    # Fetch from arXiv if not enough results and not cached
    if local_count < req.num_papers and not _is_cache_valid(normalized):
        logger.info(f"  Fetching from arXiv for '{normalized}'")
        max_res = max(100, req.num_papers * 2)
        try:
            ingest_papers_from_arxiv(normalized, max_results=max_res)
            fetch_cache[normalized] = datetime.now()

            # Re-rank after ingestion
            all_papers = db.query(PaperModel).all()
            ranked = rank_papers(normalized, all_papers)
            logger.info(f"  After fetch, relevant matches: {len(ranked)}")
        except Exception as e:
            logger.error(f"  arXiv fetch failed: {e}")

    # --- FALLBACK: if still not enough results, pad with latest papers ---
    if len(ranked) < req.num_papers:
        ranked_ids = {id(p) for p in ranked}
        remaining = sorted(
            [p for p in all_papers if id(p) not in ranked_ids],
            key=lambda p: (p.year or 0),
            reverse=True,
        )
        needed = req.num_papers - len(ranked)
        ranked.extend(remaining[:needed])
        logger.info(f"  Fallback: padded with {min(needed, len(remaining))} latest papers")

    # Apply purpose-aware logic
    purpose_lower = req.purpose.lower()
    response_data: Dict[str, Any] = {"topic": req.topic, "purpose": req.purpose}

    safe_ranked: List[Any] = list(ranked)

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
# GET /analytics/filter
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
    search_term = q or keyword
    logger.info(f"GET /analytics/filter – search='{search_term}', year_min={year_min}, year_max={year_max}")

    # Broad fetch, then filter in Python
    query = db.query(PaperModel)
    if year_min:
        query = query.filter(PaperModel.year >= year_min)
    if year_max:
        query = query.filter(PaperModel.year <= year_max)

    papers = query.all()

    # Domain filter
    if domains:
        domain_list = [d.strip().lower() for d in domains.split(",") if d.strip()]
        papers = [
            p for p in papers
            if any(d in [x.lower() for x in (p.domains or [])] for d in domain_list)
        ]

    # Soft-match ranking
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
    # Use query normalization and variants for broader matching
    variants = get_query_variants(keyword)
    papers = db.query(PaperModel).all()
    yearly_counts: Dict[int, int] = {}

    for p in papers:
        kw_list = [k.lower() for k in (p.keywords or [])]
        title = (p.title or "").lower()
        abstract = (p.abstract or "").lower()
        domains = [d.lower() for d in (p.domains or [])]

        matched = False
        for v in variants:
            if v in kw_list or v in title or v in abstract or v in domains:
                matched = True
                break

        if matched:
            y = p.year
            if y is not None:
                yearly_counts[y] = yearly_counts.get(y, 0) + 1

    # If no trend data found, return overall yearly distribution as fallback
    if not yearly_counts:
        logger.info(f"  keyword-trend: no data for '{keyword}', returning overall distribution")
        for p in papers:
            y = p.year
            if y is not None:
                yearly_counts[y] = yearly_counts.get(y, 0) + 1

    return {"keyword": keyword, "yearly_counts": yearly_counts}

# -------------------------------------------------------------------
# GET /export/tableau-data
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
            writer.writerow([p.title or "Untitled", p.year or 0, p_domain, keywords_str])
            yield output.getvalue()
            output.seek(0)
            output.truncate(0)

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=tableau_export.csv"}
    )

# -------------------------------------------------------------------
# GET /system/stats
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
