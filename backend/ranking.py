from datetime import datetime

def rank_papers(query: str, papers: list) -> list:
    """
    Ranks papers based on title match, abstract match, and recency.
    Weights: 0.6 title, 0.3 abstract, 0.1 recency
    """
    if not query:
        return sorted(papers, key=lambda p: p.year, reverse=True)
        
    query_lower = query.lower()
    current_year = datetime.now().year
    
    scored_papers = []
    
    for paper in papers:
        # Title score (basic matching)
        title_lower = paper.title.lower() if paper.title else ""
        title_score = 1.0 if query_lower in title_lower else 0.0
        
        # Abstract score
        abstract_lower = paper.abstract.lower() if paper.abstract else ""
        abstract_score = 1.0 if query_lower in abstract_lower else 0.0
        
        # Recency score normalized: (year - 2000) / (current_year - 2000)
        # Bounded between 0 and 1
        year = paper.year if paper.year else 2000
        recency_score = max(0.0, min(1.0, (year - 2000) / max(1, current_year - 2000)))
        
        # Combined score
        combined_score = (0.6 * title_score) + (0.3 * abstract_score) + (0.1 * recency_score)
        
        scored_papers.append((combined_score, paper))
        
    # Sort descending by score, string tie-breaker
    scored_papers.sort(key=lambda x: (x[0], x[1].year), reverse=True)
    
    return [p for score, p in scored_papers]
