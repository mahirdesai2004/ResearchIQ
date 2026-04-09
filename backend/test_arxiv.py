import arxiv
search = arxiv.Search(query='all:"machine learning"', max_results=5)
for res in arxiv.Client().results(search):
    print(res.title)
