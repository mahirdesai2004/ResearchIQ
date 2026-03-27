import arxiv
import logging
import asyncio
from datetime import datetime
from database import SessionLocal, PaperModel
from keyword_extractor import extract_keywords
import os
import requests

logger = logging.getLogger(__name__)

import threading
import time as _time

# Global S2 rate limiter: enforces 1.1s minimum gap between API calls
_s2_lock = threading.Lock()
_s2_last_call = 0.0

def _rate_limit_s2():
    """Wait if needed to respect S2 rate limit (1 req/sec)."""
    global _s2_last_call
    with _s2_lock:
        now = _time.monotonic()
        elapsed = now - _s2_last_call
        if elapsed < 1.1:
            _time.sleep(1.1 - elapsed)
        _s2_last_call = _time.monotonic()

S2_KEYS = [k.strip() for k in os.environ.get("S2_API_KEYS", "").split(",") if k.strip()]
_s2_idx = 0

def get_s2_headers():
    global _s2_idx
    if not S2_KEYS:
        return {}
    key = S2_KEYS[_s2_idx]
    _s2_idx = (_s2_idx + 1) % len(S2_KEYS)
    return {"x-api-key": key}

def ingest_quick_s2(topic: str, max_results: int = 40):
    """
    Fast ingestion from Semantic Scholar API with exponential backoff.
    Works without API keys (anonymous tier: ~1 req/sec).
    With keys: higher rate limits.
    """

    import time
    db = SessionLocal()
    added_count = 0

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params = {
        "query": topic,
        "limit": max_results,
        "fields": "title,abstract,authors,year,publicationDate,externalIds,citationCount"
    }

    # Exponential backoff: 3 retries (2s, 4s, 8s) with rate limiting
    results = []
    for attempt in range(3):
        try:
            _rate_limit_s2()
            response = requests.get(url, params=params, headers=get_s2_headers(), timeout=15)
            if response.status_code == 200:
                data = response.json()
                results = data.get("data", [])
                logger.info(f"S2 API success: {len(results)} papers for '{topic}'")
                break
            elif response.status_code == 429:
                wait = 2 ** (attempt + 1)  # 2s, 4s, 8s
                logger.warning(f"S2 API 429 — retry {attempt+1}/3 in {wait}s")
                time.sleep(wait)
            else:
                logger.warning(f"S2 API error {response.status_code}: {response.text[:200]}")
                break
        except Exception as e:
            logger.warning(f"S2 API exception: {e}")
            break

    if not results:
        db.close()
        return {"topic": topic, "fetched": 0, "added": 0, "source": "api_failed"}

    existing_ids = {row[0] for row in db.query(PaperModel.id).all()}
    new_papers = []

    for result in results:
        entry_id = result.get("paperId")
        if not entry_id or entry_id in existing_ids:
            continue

        title = (result.get("title") or "").replace("\n", " ").strip()
        if not title:
            title = "No title"

        abstract = (result.get("abstract") or "").replace("\n", " ").strip()
        authors = [a.get("name") for a in result.get("authors", []) if a.get("name")]
        pub_year = result.get("year") or datetime.now().year
        citation_count = result.get("citationCount") or 0

        pub_date_str = result.get("publicationDate")
        pub_date = datetime.now().date()
        if pub_date_str:
            try:
                pub_date = datetime.strptime(pub_date_str, "%Y-%m-%d").date()
            except Exception:
                pass

        keywords = extract_keywords(title)
        if not keywords:
            keywords = [w.lower() for w in title.split() if len(w) > 3][:3]

        paper = PaperModel(
            id=entry_id,
            title=title,
            abstract=abstract,
            authors=authors,
            year=pub_year,
            published=pub_date,
            source="semanticscholar",
            domains=[topic],
            keywords=keywords,
            summary=None,
            citation_count=citation_count
        )

        new_papers.append(paper)
        existing_ids.add(entry_id)
        added_count += 1

    if new_papers:
        db.bulk_save_objects(new_papers)
        db.commit()

    logger.info(f"S2 API ingested {added_count} papers for '{topic}'")
    db.close()
    return {"topic": topic, "fetched": added_count, "added": added_count, "source": "api"}


def fetch_openalex(topic: str, max_results: int = 15):
    """Fallback fetcher using OpenAlex API (no key required)"""
    url = f"https://api.openalex.org/works?search={topic}&per-page={max_results}"
    results = []
    try:
        response = requests.get(url, timeout=12)
        if response.status_code == 200:
            data = response.json().get("results", [])
            for item in data:
                title = item.get("title")
                if not title: continue
                
                abstract = ""
                idx = item.get("abstract_inverted_index")
                if idx:
                    # reconstruct abstract
                    words = []
                    for k, v in idx.items():
                        for pos in v:
                            while len(words) <= pos:
                                words.append("")
                            words[pos] = k
                    abstract = " ".join(words)
                
                authors = [a.get("author", {}).get("display_name") for a in item.get("authorships", []) if a.get("author")]
                pub_year = item.get("publication_year", datetime.now().year)
                results.append({
                    "id": item.get("id", "").split("/")[-1],
                    "title": title,
                    "abstract": abstract.strip(),
                    "authors": authors,
                    "year": pub_year,
                    "source": "openalex",
                    "citation_count": item.get("cited_by_count", 0)
                })
    except Exception as e:
        logger.warning(f"OpenAlex fetch error: {e}")
    return results


def fetch_crossref(topic: str, max_results: int = 15):
    """Absolute backstop fetcher using CrossRef API"""
    url = f"https://api.crossref.org/works?query={topic}&select=title,abstract,author,published,DOI,is-referenced-by-count&rows={max_results}"
    results = []
    try:
        response = requests.get(url, timeout=12)
        if response.status_code == 200:
            data = response.json().get("message", {}).get("items", [])
            for item in data:
                title_list = item.get("title", [])
                title = title_list[0] if title_list else ""
                if not title: continue
                
                abstract = item.get("abstract", "")
                import re
                abstract = re.sub(r'<[^>]+>', '', abstract) # remove JATS tags
                
                authors = []
                for a in item.get("author", []):
                    name = f"{a.get('given', '')} {a.get('family', '')}".strip()
                    if name: authors.append(name)
                    
                pub_year = datetime.now().year
                pub_parts = item.get("published", {}).get("date-parts", [[]])[0]
                if pub_parts:
                    pub_year = pub_parts[0]
                    
                # Use a timestamp if DOI is missing
                import time
                doi = item.get("DOI", str(time.time()).replace('.',''))
                
                results.append({
                    "id": doi,
                    "title": title,
                    "abstract": abstract.strip(),
                    "authors": authors,
                    "year": pub_year,
                    "source": "crossref",
                    "citation_count": item.get("is-referenced-by-count", 0)
                })
    except Exception as e:
        logger.warning(f"CrossRef fetch error: {e}")
    return results


def score_paper(paper_data: dict, topic: str) -> int:
    """Strict relevance scoring (+2 Title, +1 Abstract)"""
    terms = [t.lower() for t in topic.split() if len(t) > 2]
    if not terms:
        return 5 # Safe default if query is entirely short words
        
    score = 0
    t_text = paper_data.get("title", "").lower()
    a_text = paper_data.get("abstract", "").lower()
    
    for t in terms:
        if t in t_text:
            score += 2
        if t in a_text:
            score += 1
            
    return score



def fallback_db_search(topic: str, db, limit: int = 20):
    """
    Broad SQLite LIKE search on title and abstract columns.
    Requires at least 2 query terms to match (or all terms if query has only 1 word).
    """
    terms = [t for t in topic.lower().split() if len(t) > 2]
    min_matches = min(2, len(terms))  # require 2+ matches, or all if single term
    all_papers = db.query(PaperModel).all()
    scored = []

    for p in all_papers:
        text = ((p.title or "") + " " + (p.abstract or "")).lower()
        match_count = sum(1 for t in terms if t in text)
        if match_count >= min_matches:
            scored.append((p, match_count))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, _ in scored[:limit]]


def get_top_cached(db, limit: int = 10):
    """
    Absolute last resort: return the most-cited papers from the entire DB.
    """
    papers = db.query(PaperModel).order_by(
        PaperModel.citation_count.desc()
    ).limit(limit).all()
    if not papers:
        papers = db.query(PaperModel).order_by(
            PaperModel.year.desc()
        ).limit(limit).all()
    return papers

def ingest_by_year(topic: str, start_year=2018, end_year=2026):
    """
    Ingest papers for a specific topic across multiple years to ensure true trends.
    """
    client = arxiv.Client()
    db = SessionLocal()
    added_count = 0

    for year in range(start_year, end_year + 1):
        query_str = f"\"{topic}\" AND submittedDate:[{year}01010000 TO {year}12312359]"

        search = arxiv.Search(
            query=query_str,
            max_results=50,
        )

        try:
            results = list(client.results(search))
        except Exception as e:
            logger.warning(f"arXiv fetch failed for year {year}: {e}")
            continue

        existing_ids = {row[0] for row in db.query(PaperModel.id).all()}
        new_papers = []

        for result in results:
            entry_id = result.entry_id.split("/")[-1] if result.entry_id else result.get_short_id()
            if entry_id in existing_ids:
                continue

            title = (result.title or "").replace("\n", " ").strip()
            if not title or title.lower() == "untitled":
                title = "No title"

            abstract = (result.summary or "").replace("\n", " ").strip()

            authors = [a.name for a in result.authors] if result.authors else []
            pub_year = result.published.year if result.published else year
            pub_date = result.published.date() if result.published else datetime.now().date()
            keywords = extract_keywords(title)
            
            # Additional fallback to avoid empty keywords
            if not keywords:
                keywords = [w.lower() for w in title.split() if len(w) > 3][:3]

            paper = PaperModel(
                id=entry_id,
                title=title,
                abstract=abstract,
                authors=authors,
                year=pub_year,
                published=pub_date,
                source="arxiv",
                domains=[topic],
                keywords=keywords,
                summary=None
            )

            new_papers.append(paper)
            existing_ids.add(entry_id)
            added_count += 1

        if new_papers:
            db.bulk_save_objects(new_papers)
            db.commit()

        logger.info(f"Ingested {len(new_papers)} papers for '{topic}' in year {year}")

    db.close()
    
    return {
        "topic": topic,
        "fetched": added_count,  # Total added over all years
        "added": added_count
    }

def ingest_quick(topic: str, max_results: int = 40):
    """
    Fast, single-batch ingestion for dynamically requested queries.
    """
    client = arxiv.Client()
    db = SessionLocal()
    added_count = 0

    search = arxiv.Search(
        query=topic,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    try:
        results = list(client.results(search))
    except Exception as e:
        logger.warning(f"Quick arXiv fetch failed: {e}")
        db.close()
        return {"topic": topic, "fetched": 0, "added": 0}

    existing_ids = {row[0] for row in db.query(PaperModel.id).all()}
    new_papers = []

    for result in results:
        entry_id = result.entry_id.split("/")[-1] if result.entry_id else result.get_short_id()
        if entry_id in existing_ids:
            continue

        title = (result.title or "").replace("\n", " ").strip()
        if not title or title.lower() == "untitled":
            title = "No title"

        abstract = (result.summary or "").replace("\n", " ").strip()
        authors = [a.name for a in result.authors] if result.authors else []
        pub_year = result.published.year if result.published else datetime.now().year
        pub_date = result.published.date() if result.published else datetime.now().date()
        keywords = extract_keywords(title)
        
        if not keywords:
            keywords = [w.lower() for w in title.split() if len(w) > 3][:3]

        paper = PaperModel(
            id=entry_id,
            title=title,
            abstract=abstract,
            authors=authors,
            year=pub_year,
            published=pub_date,
            source="arxiv",
            domains=[topic],
            keywords=keywords,
            summary=None
        )

        new_papers.append(paper)
        existing_ids.add(entry_id)
        added_count += 1

    if new_papers:
        db.bulk_save_objects(new_papers)
        db.commit()

    logger.info(f"Quick ingested {len(new_papers)} papers for '{topic}'")
    db.close()
    
    return {"topic": topic, "fetched": added_count, "added": added_count}

def ingest_papers_from_arxiv(topic: str, max_results: int = 50) -> dict:
    # Delegate to ingest_by_year to ensure multi-year representation
    _ = max_results 
    return ingest_by_year(topic, start_year=2018, end_year=2026)

async def ingest_papers_from_arxiv_async(topic: str, max_results: int = 50) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ingest_papers_from_arxiv, topic, max_results)
