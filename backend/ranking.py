import re
from query_parser import normalize

def score_and_filter(papers, query_terms):
    results = []

    important_terms = [t for t, w in query_terms.items() if w >= 3]
    bigrams = [t for t in query_terms if "_" in t]

    for p in papers:
        text = normalize((p.title or "") + " " + (p.abstract or ""))

        score = 0
        matched = []

        for term, weight in query_terms.items():
            if term in text:
                score += weight
                matched.append(term)

        # HARD FILTER 1: must match at least one important term
        if not any(t in matched for t in important_terms):
            continue

        # HARD FILTER 2: enforce phrase relevance if bigrams exist
        if bigrams and not any(bg in text for bg in bigrams):
            continue

        # HARD FILTER 3: minimum score
        if score < 3:
            continue

        results.append((p, score, matched))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
