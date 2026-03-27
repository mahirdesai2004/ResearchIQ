def find_gaps(papers):
    """
    Analyze papers to identify research gaps as full descriptive sentences.
    Returns a list of gap description strings.
    """
    if not papers:
        return []

    # Collect all keywords across papers
    keyword_count = {}
    all_keywords = set()
    topic_areas = set()

    for p in papers:
        if not p.keywords:
            continue
        for kw in p.keywords:
            kw_lower = str(kw).lower().strip()
            if len(kw_lower) > 2:
                keyword_count[kw_lower] = keyword_count.get(kw_lower, 0) + 1
                all_keywords.add(kw_lower)
        # Collect domain areas
        if p.domains:
            for d in p.domains:
                topic_areas.add(str(d).lower())

    # Under-represented keywords (appear in < 3 papers) = potential gaps
    rare_keywords = [k for k, v in keyword_count.items() if v < 3 and len(k) > 3]
    rare_keywords.sort(key=lambda k: keyword_count[k])

    # Well-studied keywords (appear in many papers)
    common_keywords = [k for k, v in sorted(keyword_count.items(), key=lambda x: -x[1]) if v >= 3]

    # Generate meaningful gap sentences
    gaps = []

    # Gap type 1: Under-explored subtopics
    if rare_keywords:
        batch1 = rare_keywords[:3]
        for kw in batch1:
            gaps.append(f"Limited research exists on \"{kw}\" — only {keyword_count[kw]} paper(s) in this corpus address it directly.")

    # Gap type 2: Cross-domain integration
    if len(common_keywords) >= 2:
        gaps.append(f"Few studies combine \"{common_keywords[0]}\" with \"{common_keywords[1]}\" in a unified framework, suggesting an under-explored intersection.")

    # Gap type 3: Methodology gaps
    method_terms = {"benchmark", "evaluation", "comparison", "scalability", "real-time", "deployment", "reproducibility"}
    missing_methods = method_terms - all_keywords
    if missing_methods:
        sample = list(missing_methods)[:2]
        gaps.append(f"Topics like {' and '.join(sample)} are underrepresented, indicating a potential gap in practical validation.")

    # Gap type 4: Temporal gaps
    years = [p.year for p in papers if p.year]
    if years:
        recent = sum(1 for y in years if y >= 2023)
        total = len(years)
        if recent < total * 0.3:
            gaps.append(f"Only {recent} of {total} papers are from 2023 or later, suggesting the field may benefit from more up-to-date research.")

    # Gap type 5: General coverage
    if not gaps:
        gaps.append("The current literature shows broad coverage but lacks focused deep-dive studies on emerging sub-areas.")

    return gaps[:6]
