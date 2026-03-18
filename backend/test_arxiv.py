import arxiv

try:
    search = arxiv.Search(
        query="all:\"artificial intelligence\" AND submittedDate:[201801010000 TO 201812312359]",
        max_results=5,
    )
    client = arxiv.Client()
    results = list(client.results(search))
    print("Found with HHMM syntax:", len(results))
except Exception as e:
    print("Error HHMM:", e)

try:
    search2 = arxiv.Search(
        query="all:\"artificial intelligence\"",
        max_results=5,
    )
    results2 = list(client.results(search2))
    print("Found without date:", len(results2))
except Exception as e:
    print("Error without date:", e)
