from datetime import datetime
from typing import List, Dict

# -------------------------------------------------------------------
# Synonym map: short forms → full forms
# -------------------------------------------------------------------
SYNONYMS: Dict[str, str] = {
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "llm": "large language model",
    "dl": "deep learning",
    "rl": "reinforcement learning",
    "gan": "generative adversarial network",
    "cnn": "convolutional neural network",
    "rnn": "recurrent neural network",
    "transformer": "transformer",
    "bert": "bert",
    "gpt": "gpt",
}

# Reverse map too: full forms → short forms
REVERSE_SYNONYMS: Dict[str, str] = {v: k for k, v in SYNONYMS.items()}

def normalize_query(query: str) -> str:
    """Lowercase, strip, and expand synonyms."""
    q = query.lower().strip()
    # If the query IS a known abbreviation, expand it
    if q in SYNONYMS:
        return SYNONYMS[q]
    return q

def get_query_variants(query: str) -> List[str]:
    """
    Returns a list of search variants for a query:
    - the normalized full query
    - the abbreviation (if any)
    - individual tokens (words longer than 2 chars)
    """
    normalized = normalize_query(query)
    variants = [normalized]

    # Add abbreviation if the normalized form has a reverse synonym
    if normalized in REVERSE_SYNONYMS:
        variants.append(REVERSE_SYNONYMS[normalized])

    # Add the original lowered form if different
    original_lower = query.lower().strip()
    if original_lower not in variants:
        variants.append(original_lower)

    # Split into tokens (words > 2 chars)
    tokens = [t for t in normalized.split() if len(t) > 2]
    for t in tokens:
        if t not in variants:
            variants.append(t)

    return variants

def score_paper(query_variants: List[str], paper) -> float:
    """
    Scores a paper against query variants using soft matching.
    Title match = strong, abstract match = medium, keyword/domain match = light, recency = bonus.
    """
    title_lower = (paper.title or "").lower()
    abstract_lower = (paper.abstract or "").lower()
    kw_list = [k.lower() for k in (paper.keywords or [])]
    domain_list = [d.lower() for d in (paper.domains or [])]

    current_year = datetime.now().year
    year = paper.year if paper.year else 2000
    recency = max(0.0, min(1.0, (year - 2000) / max(1, current_year - 2000)))

    title_score = 0.0
    abstract_score = 0.0
    keyword_score = 0.0
    domain_score = 0.0

    for v in query_variants:
        if v in title_lower:
            title_score = max(title_score, 1.0)
        if v in abstract_lower:
            abstract_score = max(abstract_score, 1.0)
        if v in kw_list:
            keyword_score = max(keyword_score, 0.8)
        if v in domain_list:
            domain_score = max(domain_score, 0.7)

    # Weighted combination
    combined = (
        0.40 * title_score +
        0.25 * abstract_score +
        0.15 * keyword_score +
        0.10 * domain_score +
        0.10 * recency
    )
    return combined

def rank_papers(query: str, papers: list) -> list:
    """
    Ranks papers using soft matching with synonym expansion and token splitting.
    Returns papers sorted by relevance score descending.
    Only includes papers with score > 0 (at least some match).
    """
    if not query:
        return sorted(papers, key=lambda p: (p.year or 0), reverse=True)

    variants = get_query_variants(query)

    scored = []
    for paper in papers:
        s = score_paper(variants, paper)
        scored.append((s, paper))

    # Sort by score desc, then year desc
    scored.sort(key=lambda x: (x[0], x[1].year or 0), reverse=True)

    # Return only papers with some relevance (score > 0)
    return [p for score, p in scored if score > 0]
