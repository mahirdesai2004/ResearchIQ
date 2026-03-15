import arxiv
import logging
import asyncio
from datetime import datetime
from database import SessionLocal, PaperModel
from keyword_extractor import extract_keywords

logger = logging.getLogger(__name__)

def ingest_papers_from_arxiv(topic: str, max_results: int = 50) -> dict:
    """
    Fetches papers from arXiv, extracts keywords, and stores them in DB.
    Deduplicates using paper id. Ensures data quality on every paper.
    """
    client = arxiv.Client()
    search = arxiv.Search(
        query=topic,
        max_results=max_results,
        sort_by=arxiv.SortCriterion.SubmittedDate
    )

    db = SessionLocal()
    added_count: int = 0
    total_fetched: int = 0

    try:
        results = list(client.results(search))
        total_fetched = len(results)

        existing_ids = {row[0] for row in db.query(PaperModel.id).all()}

        new_papers = []
        for r in results:
            entry_id = r.entry_id.split("/")[-1] if r.entry_id else r.get_short_id()
            if entry_id in existing_ids:
                continue

            # --- Data quality guards ---
            raw_title = (r.title or "").replace("\n", " ").strip()
            title = raw_title if raw_title and raw_title.lower() != "untitled" else "Untitled"

            raw_abstract = (r.summary or "").replace("\n", " ").strip()
            abstract = raw_abstract if raw_abstract else "No abstract available."

            authors = [a.name for a in r.authors] if r.authors else []
            year = r.published.year if r.published else datetime.now().year
            pub_date = r.published.date() if r.published else datetime.now().date()

            keywords = extract_keywords(title)
            # Ensure keywords is never empty — use first 3 title words as fallback
            if not keywords:
                fallback_words = [w.lower() for w in title.split() if len(w) > 2]
                keywords = fallback_words[:3] if fallback_words else ["research"]

            p = PaperModel(
                id=entry_id,
                title=title,
                abstract=abstract,
                authors=authors,
                published=pub_date,
                year=year,
                source="arxiv",
                domains=[topic],
                keywords=keywords,
                summary=None
            )
            new_papers.append(p)
            existing_ids.add(entry_id)
            added_count += 1

        if new_papers:
            db.bulk_save_objects(new_papers)
            db.commit()

        logger.info(f"Ingested {added_count} new papers for topic '{topic}' (fetched {total_fetched})")

    except Exception as e:
        db.rollback()
        logger.error(f"Failed arxiv ingestion for {topic}: {e}")
        raise
    finally:
        db.close()

    return {
        "topic": topic,
        "fetched": total_fetched,
        "added": added_count
    }

async def ingest_papers_from_arxiv_async(topic: str, max_results: int = 50) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ingest_papers_from_arxiv, topic, max_results)
