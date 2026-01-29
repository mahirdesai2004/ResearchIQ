import requests
import xml.etree.ElementTree as ET
from fastapi import FastAPI, Query
import json
from pathlib import Path
from typing import List, Dict, Any

app = FastAPI(title="ResearchIQ Backend")

def parse_arxiv_entry(entry: ET.Element) -> Dict[str, Any]:
    """Helper to parse a single arXiv entry XML element."""
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}
    
    # Extract title
    title_elem = entry.find('atom:title', namespace)
    title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None and title_elem.text else "Untitled"
    
    # Extract summary (abstract)
    summary_elem = entry.find('atom:summary', namespace)
    abstract = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None and summary_elem.text else "No abstract available"
    
    # Extract published year
    published_elem = entry.find('atom:published', namespace)
    published_year = published_elem.text[:4] if published_elem is not None and published_elem.text else "Unknown"
    
    return {
        "title": title,
        "abstract": abstract,
        "published_year": published_year,
        "source": "arxiv"
    }

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
        output_file = Path("data/papers.json")
        existing_data = []
        if output_file.exists():
            try:
                with open(output_file, "r") as f:
                    existing_data = json.load(f)
            except json.JSONDecodeError:
                pass  # Ignore invalid JSON, start fresh
        
        existing_data.extend(papers)
        
        with open(output_file, "w") as f:
            json.dump(existing_data, f, indent=2)
            
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
