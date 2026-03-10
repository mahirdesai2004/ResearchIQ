import requests
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import json
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter
import re

from utils import parse_arxiv_entry, load_papers, save_papers, summarize_abstract, fetch_arxiv_papers, logger

app = FastAPI(title="ResearchIQ Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Welcome to ResearchIQ API"}

def get_domain_from_query(query: str) -> str:
    query_lower = query.lower()
    mapping = {
        "artificial intelligence": "AI",
        "machine learning": "ML",
        "large language models": "LLM",
        "nlp": "NLP",
        "computer vision": "CV"
    }
    for k, v in mapping.items():
        if k in query_lower:
            return v
    return "Other"

@app.get("/papers/arxiv")
def get_arxiv_papers(
    query: str = Query("ai", description="Search query for arXiv"),
    max_results: int = Query(50, description="Number of results to return")
):
    """
    Fetch research papers from arXiv API.
    """
    logger.info(f"Handling /papers/arxiv request - Query: {query}, Max Results: {max_results}")
    
    try:
        domain = get_domain_from_query(query)
        logger.info(f"Assigned domain '{domain}' for query '{query}'")
        papers = fetch_arxiv_papers(query, max_results, domain=domain)
        
        # Save to local file
        existing_data = load_papers()
        
        # Deduplication using paper_id
        existing_ids = {p.get("paper_id") for p in existing_data if p.get("paper_id")}
        
        added_count = 0
        for p in papers:
            if p.get("paper_id") not in existing_ids:
                existing_data.append(p)
                added_count += 1
        
        if added_count > 0:
            save_papers(existing_data)
            
        logger.info(f"Successfully fetched {len(papers)} papers, added {added_count} new unique papers.")
            
        return {
            "query": query,
            "domain": domain,
            "count": added_count,
            "fetched": len(papers),
            "papers": papers,
            "message": f"Added {added_count} new papers to data/papers.json"
        }
        
    except requests.RequestException as e:
        logger.error(f"Failed to fetch from arXiv: {str(e)}")
        return {"error": f"Failed to fetch from arXiv: {str(e)}"}
    except ET.ParseError as e:
        logger.error(f"Failed to parse arXiv response: {str(e)}")
        return {"error": f"Failed to parse arXiv response: {str(e)}"}

@app.post("/papers/arxiv/batch")
def batch_ingest_arxiv_papers():
    """
    Batch ingest papers for a predefined set of key topics.
    """
    logger.info("Handling /papers/arxiv/batch request")
    topics = [
        "artificial intelligence", 
        "machine learning", 
        "large language models", 
        "nlp", 
        "computer vision"
    ]
    
    total_fetched = 0
    total_added = 0
    
    try:
        existing_data = load_papers()
        existing_ids = {p.get("paper_id") for p in existing_data if p.get("paper_id")}
        
        for topic in topics:
            domain = get_domain_from_query(topic)
            logger.info(f"Batch fetching for topic '{topic}' -> Domain '{domain}'")
            papers = fetch_arxiv_papers(query=topic, max_results=50, domain=domain)
            total_fetched += len(papers)
            
            for p in papers:
                if p.get("paper_id") not in existing_ids:
                    existing_data.append(p)
                    existing_ids.add(p.get("paper_id"))
                    total_added += 1
                    
        if total_added > 0:
            save_papers(existing_data)
            
        logger.info(f"Batch ingestion complete. Fetched: {total_fetched}, Added: {total_added}")
        return {
            "message": "Batch ingestion complete",
            "topics_processed": topics,
            "total_fetched": total_fetched,
            "total_added": total_added
        }
    except Exception as e:
        logger.error(f"Error during batch ingestion: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error during batch ingestion")

@app.get("/system/stats")
def get_system_stats():
    """
    Returns high-level statistics about the stored research papers.
    """
    logger.info("Handling /system/stats request")
    try:
        papers = load_papers()
        total_papers = len(papers)
        
        years = set()
        for p in papers:
            y = p.get("published_year")
            if y and y.isdigit():
                years.add(int(y))
                
        if years:
            earliest_year = min(years)
            latest_year = max(years)
            years_available = sorted(list(set(years)))
        else:
            earliest_year = None
            latest_year = None
            years_available = []
            
        return {
            "total_papers": total_papers,
            "years_available": years_available,
            "earliest_year": earliest_year,
            "latest_year": latest_year
        }
    except Exception as e:
        logger.error(f"Error in get_system_stats: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/analytics/yearly-count")
def get_yearly_count():
    """
    Aggregate research papers by their published year.
    Returns a count of papers for each year.
    """
    logger.info("Handling /analytics/yearly-count request")
    try:
        papers = load_papers()
        yearly_counts = {}
        
        for paper in papers:
            year = paper.get("published_year", "Unknown")
            yearly_counts[year] = yearly_counts.get(year, 0) + 1
            
        return {"yearly_counts": yearly_counts}
    except Exception as e:
        logger.error(f"Error in get_yearly_count: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/analytics/recent-papers")
def get_recent_papers(limit: int = Query(10, description="Number of recent papers to return")):
    """
    Returns the most recent papers sorted by published_year descending.
    """
    logger.info(f"Handling /analytics/recent-papers request - Limit: {limit}")
    try:
        papers = load_papers()
        # Sort by published_year descending (assuming year is string like '2024')
        sorted_papers = sorted(
            papers, 
            key=lambda x: x.get("published_year", ""), 
            reverse=True
        )
        recent = sorted_papers[:limit]
        
        return {
            "count": len(recent),
            "papers": recent
        }
    except Exception as e:
        logger.error(f"Error in get_recent_papers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/analytics/filter")
def filter_papers(
    year: str = Query(None, description="Filter by published year"),
    keyword: str = Query(None, description="Filter by keyword in title or abstract"),
    limit: int = Query(20, description="Number of results to return"),
    offset: int = Query(0, description="Number of results to skip")
):
    """
    Filter stored papers by published year and/or keyword.
    """
    logger.info(f"Handling /analytics/filter request - Year: {year}, Keyword: {keyword}")
    try:
        papers = load_papers()

        filtered_papers = []
        for paper in papers:
            if year and paper.get("published_year") != year:
                continue
            if keyword:
                kw = keyword.lower()
                title = paper.get("title", "").lower()
                abstract = paper.get("abstract", "").lower()
                if kw not in title and kw not in abstract:
                    continue
            filtered_papers.append(paper)

        paginated_papers = filtered_papers[offset:offset+limit]
        logger.info(f"Found {len(filtered_papers)} matching papers, returning {len(paginated_papers)}.")

        return {
            "count": len(filtered_papers),
            "returned": len(paginated_papers),
            "papers": paginated_papers
        }
    except Exception as e:
        logger.error(f"Error in filter_papers: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/analytics/summaries")
def get_summaries():
    """
    Returns a list of papers including an LLM-ready summary.
    Summaries are generated and cached to avoid recomputation.
    """
    logger.info("Handling /analytics/summaries request")
    try:
        papers = load_papers()
        updated = False
        
        for paper in papers:
            if "summary" not in paper:
                paper["summary"] = summarize_abstract(paper.get("abstract", ""))
                updated = True
                
        if updated:
            save_papers(papers)
            logger.info("New summaries generated and saved to papers.json")
            
        return {
            "count": len(papers),
            "papers": [
                {
                    "title": p.get("title", "Untitled"),
                    "published_year": p.get("published_year", "Unknown"),
                    "summary": p.get("summary", "No summary available.")
                }
                for p in papers
            ]
        }
    except Exception as e:
        logger.error(f"Error in get_summaries: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/analytics/keyword-trend")
def get_keyword_trend(keyword: str = Query(..., description="Keyword to track trends for")):
    """
    Analyzes the frequency of a specific keyword across publication years.
    Returns the yearly counts of the keyword appearing in titles or abstracts.
    """
    logger.info(f"Handling /analytics/keyword-trend request - Keyword: {keyword}")
    try:
        papers = load_papers()
        yearly_counts = {}
        
        kw = keyword.lower()
        for paper in papers:
            title = paper.get("title", "").lower()
            abstract = paper.get("abstract", "").lower()
            
            if kw in title or kw in abstract:
                year = paper.get("published_year", "Unknown")
                yearly_counts[year] = yearly_counts.get(year, 0) + 1
                
        return {
            "keyword": keyword,
            "yearly_counts": yearly_counts
        }
    except Exception as e:
        logger.error(f"Error in get_keyword_trend: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/analytics/top-keywords")
def get_top_keywords(
    limit: int = Query(10, description="Number of top keywords to return"),
    min_length: int = Query(3, description="Minimum length of a keyword")
):
    """
    Computes the most frequent keywords appearing in the titles of all stored papers.
    """
    logger.info(f"Handling /analytics/top-keywords request - Limit: {limit}")
    try:
        papers = load_papers()
        stop_words = {
            "the", "and", "of", "to", "in", "a", "is", "that", "for", "on", "it", 
            "with", "as", "by", "are", "from", "an", "be", "this", "which", "or", 
            "but", "not", "we", "can", "has", "have", "been", "was", "were", "their", 
            "these", "also", "using"
        }
        
        all_words = []
        for paper in papers:
            title = paper.get("title", "")
            # Basic tokenization: remove punctuation, lowercase, split
            words = re.findall(r'\b[a-z]{%d,}\b' % min_length, title.lower())
            # Filter out common stop words
            words = [w for w in words if w not in stop_words]
            all_words.extend(words)
            
        word_counts = Counter(all_words)
        top_keywords = [{"keyword": word, "count": count} for word, count in word_counts.most_common(limit)]
        
        return {
            "count": len(top_keywords),
            "top_keywords": top_keywords
        }
    except Exception as e:
        logger.error(f"Error in get_top_keywords: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


