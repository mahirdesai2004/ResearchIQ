from collections import Counter
from typing import List

def diversify_by_year(papers: list, num_papers: int) -> list:
    """
    Groups papers by year and takes top papers from each year in round-robin until num_papers reached.
    Ensures at most 2 papers per year for diversity.
    """
    year_map = {}
    for paper in papers:
        year_map.setdefault(paper.year, []).append(paper)
        
    # Sort years descending
    sorted_years = sorted(year_map.keys(), reverse=True)
    
    diversified = []
    year_counts = {y: 0 for y in sorted_years}
    
    while len(diversified) < num_papers:
        added_in_round = False
        for year in sorted_years:
            if len(diversified) >= num_papers:
                break
                
            papers_for_year = year_map[year]
            if len(papers_for_year) > year_counts[year] and year_counts[year] < 2:
                diversified.append(papers_for_year[year_counts[year]])
                year_counts[year] += 1
                added_in_round = True
                
        if not added_in_round:
            break
            
    return diversified

def extract_related_keywords(papers: list) -> List[str]:
    """
    Aggregates keywords from all given papers and returns the top 10 by frequency.
    """
    all_keywords = []
    for paper in papers:
        if paper.keywords:
            all_keywords.extend(paper.keywords)
            
    counts = Counter(all_keywords)
    top_10 = [word for word, count in counts.most_common(10)]
    return top_10
