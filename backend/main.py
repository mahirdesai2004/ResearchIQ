import requests
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Query, HTTPException
import json
from pathlib import Path
from typing import List, Dict, Any

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

@app.get("/analytics/yearly-count")
def get_yearly_count():
    """
    Aggregate research papers by their published year.
    Returns a count of papers for each year.
    """
    papers = load_papers()
    yearly_counts = {}
    
    for paper in papers:
        year = paper.get("published_year", "Unknown")
        yearly_counts[year] = yearly_counts.get(year, 0) + 1
        
    return {"yearly_counts": yearly_counts}

@app.get("/analytics/filter")
def filter_papers(
    year: str = Query(None, description="Filter by published year"),
    keyword: str = Query(None, description="Filter by keyword in title or abstract")
):
    """
    Filter stored papers by published year and/or keyword.
    Keyword search is case-insensitive and checks both title and abstract.
    """
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

@app.get("/analytics/summaries")
def get_summaries():
    """
    Returns a list of papers including an LLM-ready summary.
    Summaries are generated and cached to avoid recomputation.
    """
    papers = load_papers()
    updated = False
    
    for paper in papers:
        if "summary" not in paper:
            paper["summary"] = summarize_abstract(paper.get("abstract", ""))
            updated = True
            
    if updated:
        save_papers(papers)
        
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

