import re
from typing import List

STOP_WORDS = {
    "the", "and", "of", "to", "in", "a", "is", "that", "for", "on", "it", 
    "with", "as", "by", "are", "from", "an", "be", "this", "which", "or", 
    "but", "not", "we", "can", "has", "have", "been", "was", "were", "their", 
    "these", "also", "using"
}

def extract_keywords(title: str) -> List[str]:
    """
    Extracts keywords from a document title by:
    - Lowercasing the title
    - Splitting on non-alphanumeric characters
    - Removing predefined stop words
    - Removing words shorter than 3 characters
    """
    words = re.findall(r'\b[a-z0-9]{3,}\b', title.lower())
    keywords = set(w for w in words if w not in STOP_WORDS)
    return list(keywords)
