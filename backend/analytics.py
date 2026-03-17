def find_gaps(papers):
    keyword_count = {}

    for p in papers:
        if not p.keywords:
            continue

        for kw in p.keywords:
            keyword_count[kw] = keyword_count.get(kw, 0) + 1

    gaps = [k for k, v in keyword_count.items() if v < 3]

    return gaps[:10]
