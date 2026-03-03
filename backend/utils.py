import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
import os
import requests
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError
from google import genai

load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Paper(BaseModel):
    paper_id: str = "legacy_unknown"
    title: str
    abstract: str
    published_year: str
    source: str
    summary: Optional[str] = None

def parse_arxiv_entry(entry: ET.Element) -> Optional[Dict[str, Any]]:
    """Helper to parse a single arXiv entry XML element."""
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}
    
    # Extract id
    id_elem = entry.find('atom:id', namespace)
    paper_id_raw = id_elem.text if id_elem is not None else None
    paper_id = paper_id_raw.strip() if paper_id_raw else "unknown"
    if "/abs/" in paper_id:
        paper_id = paper_id.split("/abs/")[-1]

    # Extract title
    title_elem = entry.find('atom:title', namespace)
    title = title_elem.text.strip().replace('\n', ' ') if title_elem is not None and title_elem.text else "Untitled"
    
    # Extract summary (abstract)
    summary_elem = entry.find('atom:summary', namespace)
    abstract = summary_elem.text.strip().replace('\n', ' ') if summary_elem is not None and summary_elem.text else "No abstract available"
    
    # Extract published year
    published_elem = entry.find('atom:published', namespace)
    published_year = published_elem.text[:4] if published_elem is not None and published_elem.text else "Unknown"
    
    paper_dict = {
        "paper_id": paper_id,
        "title": title,
        "abstract": abstract,
        "published_year": published_year,
        "source": "arxiv"
    }
    
    # Validate
    try:
        validated_paper = Paper(**paper_dict)
        return validated_paper.model_dump(exclude_none=True)
    except ValidationError as e:
        logger.warning(f"Validation error on arXiv entry: {e}")
        return None

def fetch_arxiv_papers(query: str, max_results: int) -> List[Dict[str, Any]]:
    """Fetches and parses papers from arXiv API."""
    base_url = "http://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{query}",
        "start": 0,
        "max_results": max_results
    }
    
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    
    root = ET.fromstring(response.content)
    namespace = {'atom': 'http://www.w3.org/2005/Atom'}
    entries = root.findall('atom:entry', namespace)
    
    papers = []
    for entry in entries:
        parsed = parse_arxiv_entry(entry)
        if parsed is not None:
            papers.append(parsed)
            
    return papers

def load_papers() -> List[Dict[str, Any]]:
    """Helper to safely load papers from local JSON storage."""
    file_path = Path("data/papers.json")
    if not file_path.exists():
        logger.warning("data/papers.json not found. Returning empty list.")
        return []
    
    try:
        with open(file_path, "r") as f:
            raw_data = json.load(f)
            
        validated_data = []
        for item in raw_data:
            try:
                # Enforce schema on load
                validated_paper = Paper(**item)
                validated_data.append(validated_paper.model_dump(exclude_none=True))
            except ValidationError as e:
                logger.warning(f"Dropping invalid paper record: {item}. Error: {e}")
                
        return validated_data
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to decode papers.json: {e}")
        return []

def save_papers(papers: List[Dict[str, Any]]) -> None:
    """Helper to safely save papers to local JSON storage."""
    file_path = Path("data/papers.json")
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(file_path, "w") as f:
            json.dump(papers, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save papers: {e}")

_current_key_idx = 0

def get_next_api_key() -> tuple[Optional[str], int]:
    global _current_key_idx
    keys_env = os.environ.get("GEMINI_API_KEYS", "")
    api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
    if not api_keys:
        return None, -1
    
    key = api_keys[_current_key_idx]
    used_idx = _current_key_idx
    _current_key_idx = (_current_key_idx + 1) % len(api_keys)
    return key, used_idx

def call_llm_with_rotation(text: str) -> str:
    keys_env = os.environ.get("GEMINI_API_KEYS", "")
    api_keys = [k.strip() for k in keys_env.split(",") if k.strip()]
    
    if not api_keys:
        logger.warning("No API keys configured. Using fallback summary.")
        sentences = text.split('. ')
        return '. '.join(sentences[:min(2, len(sentences))]) + '.' if sentences else text
        
    models_to_try = ['gemini-2.5-flash', 'gemini-2.5-pro']
    
    # Try as many times as we have keys
    for _ in range(len(api_keys)):
        api_key, key_idx = get_next_api_key()
        if not api_key:
            break
            
        logger.info(f"Attempting LLM call using API key index {key_idx}")
        client = genai.Client(api_key=api_key)
        
        for model in models_to_try:
            try:
                prompt = f"Summarize the following scientific text into 2 or 3 sentences focusing strictly on the core contribution and findings:\n\n{text}"
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                if response and response.text:
                    logger.info(f"Successfully generated summary using model {model} and key index {key_idx}")
                    return response.text.strip().replace('\n', ' ')
            except Exception as e:
                logger.error(f"Failed to generate summary with model {model} using key index {key_idx}: {e}")
                continue
                
    logger.error("All API keys and models failed. Using fallback summary.")
    sentences = text.split('. ')
    return '. '.join(sentences[:min(2, len(sentences))]) + '.' if sentences else text

def summarize_abstract(abstract: str) -> str:
    """
    Real LLM summarization wrapper extracting core contribution.
    """
    if not abstract or abstract == "No abstract available":
        return "No summary available."
        
    return call_llm_with_rotation(abstract)
