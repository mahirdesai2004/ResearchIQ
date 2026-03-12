import requests
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Query, HTTPException
import json
from pathlib import Path
from typing import List, Dict, Any
from collections import Counter
import re

from utils import parse_arxiv_entry, load_papers, save_papers, summarize_abstract, logger

app = FastAPI(title="ResearchIQ Backend")

@app.get("/")
def read_root():
    return {"message": "Welcome to ResearchIQ API"}

@app.get("/papers/arxiv")
def get_arxiv_papers(
    query: str = Query("ai", description="Search query for arXiv"),
    max_results: int = Query(5, description="Number of results to return")
):
    """
    Fetch research papers from arXiv API.
    """
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results
    }
    
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.content)
        namespace = {'atom': 'http://www.w3.org/2005/Atom'}
        entries = root.findall('atom:entry', namespace)
        
        papers = []
        for entry in entries:
            papers.append(parse_arxiv_entry(entry))
        
        # Save to local file
        existing_data = load_papers()
        
        # Simple deduplication based on title to prevent duplicates when fetching again
        existing_titles = {p.get("title") for p in existing_data}
        for p in papers:
            if p.get("title") not in existing_titles:
                existing_data.append(p)
        
        save_papers(existing_data)
            
        return {
            "query": query,
            "count": len(papers),
            "papers": papers,
            "message": "Papers saved to data/papers.json"
        }
        
    except requests.RequestException as e:
        return {"error": f"Failed to fetch from arXiv: {str(e)}"}
    except ET.ParseError as e:
        return {"error": f"Failed to parse arXiv response: {str(e)}"}

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
            earliest_year = str(min(years))
            latest_year = str(max(years))
            years_available = sorted(list(set(str(y) for y in years)))
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
    keyword: str = Query(None, description="Filter by keyword in title or abstract")
):
    """
    Filter stored papers by published year and/or keyword.
    Keyword search is case-insensitive and checks both title and abstract.
    """
    logger.info(f"Handling /analytics/filter request - Year: {year}, Keyword: {keyword}")
    try:
        papers = load_papers()
        filtered_papers = []
        
        for paper in papers:
            # Year filter
            if year and paper.get("published_year") != year:
                continue
                
            # Keyword filter
            if keyword:
                kw = keyword.lower()
                title = paper.get("title", "").lower()
                abstract = paper.get("abstract", "").lower()
                if kw not in title and kw not in abstract:
                    continue
                    
            filtered_papers.append(paper)
            
        return {
            "count": len(filtered_papers),
            "papers": filtered_papers
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


