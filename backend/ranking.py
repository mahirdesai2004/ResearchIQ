def filter_and_score(papers, parsed_query):
    results = []

    for p in papers:
        text = f"{p.title or ''} {p.abstract or ''}".lower()

        score = 0
        matched = []

        for kw in parsed_query["keywords"]:
            if kw in text:
                score += 2
                matched.append(kw)

        if parsed_query["normalized"] in text:
            score += 5

        if score > 0:
            results.append((p, score, matched))

    results.sort(key=lambda x: x[1], reverse=True)
    return results
