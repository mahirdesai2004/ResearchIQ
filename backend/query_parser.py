def parse_query(query: str):
    q = query.lower().strip()

    synonyms = {
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "nlp": "natural language processing",
        "cv": "computer vision"
    }

    for k, v in synonyms.items():
        # careful with word boundaries if doing simple replace, but we stick to req
        # q = q.replace(k, v) as requested
        # Actually doing a split replace is safer, but I will do exactly what user asked
        # Wait, the user provided exact parsing logic:
        # for k, v in synonyms.items():
        #     q = q.replace(k, v)
        q = q.replace(k, v)

    tokens = [t for t in q.split() if len(t) > 2]

    return {
        "original": query,
        "normalized": q,
        "keywords": tokens
    }
