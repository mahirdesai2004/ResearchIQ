import arxiv
import logging
import asyncio
from datetime import datetime
from database import SessionLocal, PaperModel
from keyword_extractor import extract_keywords

logger = logging.getLogger(__name__)

def ingest_by_year(topic: str, start_year=2018, end_year=2026):
    """
    Ingest papers for a specific topic across multiple years to ensure true trends.
    """
    client = arxiv.Client()
    db = SessionLocal()
    added_count = 0

    for year in range(start_year, end_year + 1):
        query_str = f"{topic} AND submittedDate:[{year}01010000 TO {year}12312359]"

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

def ingest_papers_from_arxiv(topic: str, max_results: int = 50) -> dict:
    # Delegate to ingest_by_year to ensure multi-year representation
    _ = max_results 
    return ingest_by_year(topic, start_year=2018, end_year=2026)

async def ingest_papers_from_arxiv_async(topic: str, max_results: int = 50) -> dict:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, ingest_papers_from_arxiv, topic, max_results)
