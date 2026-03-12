import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging
from pydantic import BaseModel, ValidationError

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class Paper(BaseModel):
    title: str
    abstract: str
    published_year: str
    source: str
    summary: Optional[str] = None

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
    
    paper_dict = {
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
        return paper_dict # Fallback to unvalidated dict if strict parsing isn't desired, or could raise

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

def summarize_abstract(abstract: str) -> str:
    """
    Simulates summarization by extracting the first 2-3 sentences.
    Provides a placeholder for future LLM summarization.
    """
    if not abstract or abstract == "No abstract available":
        return "No summary available."
    
    # Simple heuristic to split sentences (not perfect, but works for simulation)
    # Split by '. ' to avoid splitting on decimals or acronyms (mostly)
    sentences = abstract.split('. ')
    num_sentences = min(2, len(sentences)) # take up to 2 sentences
    
    summary = '. '.join(sentences[:num_sentences])
    if not summary.endswith('.'):
        summary += '.'
        
    return summary
