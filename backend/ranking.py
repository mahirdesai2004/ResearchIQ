# pyre-ignore-all-errors
from query_parser import normalize
from query_parser import normalize

def strict_filter(papers, parsed_query):
    core_terms = parsed_query.get("core_terms", [])
    context_terms = parsed_query.get("context_terms", [])

    filtered = []

    for p in papers:
        # Added (or "") to prevent NoneType concatenations
        text = ((p.title or "") + " " + (p.abstract or "")).lower()

        core_match = sum(1 for t in core_terms if t in text)
        context_match = sum(1 for t in context_terms if t in text)

        # MUST: at least one core term
        if core_match == 0:
            continue

        # Adaptive strictness
        if len(core_terms) >= 2:
            if core_match < 2 and context_match == 0:
                continue

        filtered.append(p)

    return filtered

def compute_term_frequencies(papers):
    """Compute how many papers contain each word (document frequency)."""
    freq = {}
    for p in papers:
        text = ((p.title or "") + " " + (p.abstract or "")).lower()
        words = set(text.split())
        for w in words:
            freq[w] = freq.get(w, 0) + 1
    return freq


def score_and_filter(papers, query_terms, term_freq=None):
    """Score papers with rarity boost and hard filtering on important terms."""
    if term_freq is None:
        term_freq = compute_term_frequencies(papers)

    results = []

    important_terms = [t for t, w in query_terms.items() if w >= 5]
    core_terms = important_terms  # alias for clarity

    for p in papers:
        text = normalize((p.title or "") + " " + (p.abstract or ""))
        title_text = normalize(p.title or "")

        # HARD FILTER: must contain at least one core/important term
        if not any(term in text for term in core_terms):
            continue

        score = 0
        matched = []

        for term, weight in query_terms.items():
            if term in text:
                # Rarity boost: rare terms get massive score multiplier
                rarity = 1 / (term_freq.get(term, 1))
                score += weight * (1 + rarity * 50)
                matched.append(term)

        # HARD FILTER: must match at least one important term
        if not any(t in matched for t in important_terms):
            continue

        # HARD FILTER: reject weak-only matches (single generic term)
        if len(matched) == 1 and matched[0] in {"disease", "diseas", "detect", "classif", "applic"}:
            continue

        # HARD FILTER: minimum score
        if score < 5:
            continue

        # BOOST: exact important term in title → double score
        if any(term in title_text for term in important_terms):
            score *= 2

        results.append((p, round(score, 2), matched))

    results.sort(key=lambda x: x[1], reverse=True)

    # Debug output
    print("\n=== RANKING DEBUG ===")
    print("QUERY TERMS:", query_terms)
    print(f"TOTAL MATCHED: {len(results)} papers")
    for p, sc, m in results[:10]:
        print(f"  TITLE: {(p.title or '')[:60]}")
        print(f"  MATCHED: {m}")
        print(f"  SCORE: {sc}")
        print("  ---")

    return results


def rank_papers(papers, query: str, limit: int = 20):
    """
    Rank papers by composite score:
      score = (citation_norm * 0.5) + (recency * 0.3) + (relevance * 0.2)
    """
    from datetime import datetime
    current_year = datetime.now().year
    query_terms = [t.lower() for t in query.split() if len(t) > 2]

    scored = []
    for p in papers:
        # Citation score: normalize to [0, 1], cap at 500
        cites = getattr(p, 'citation_count', 0) or 0
        citation_norm = min(cites, 500) / 500.0

        # Recency score: linear scale [0, 1] over 10 years
        year = p.year or 2020
        recency = max(0.0, min(1.0, (year - (current_year - 10)) / 10.0))

        # Relevance score: fraction of query terms found
        text = ((p.title or "") + " " + (p.abstract or "")).lower()
        if query_terms:
            relevance = sum(1 for t in query_terms if t in text) / len(query_terms)
        else:
            relevance = 0.5

        score = (citation_norm * 0.5) + (recency * 0.3) + (relevance * 0.2)
        scored.append((p, round(score, 4)))

    scored.sort(key=lambda x: x[1], reverse=True)
    return [(p, s) for p, s in scored[:limit]]
