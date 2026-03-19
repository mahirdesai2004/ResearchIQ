# pyre-ignore-all-errors
from query_parser import normalize


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
