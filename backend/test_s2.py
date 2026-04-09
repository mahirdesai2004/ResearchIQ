import requests
url = "https://api.semanticscholar.org/graph/v1/paper/search"
params = {
    "query": "protein coagulation",
    "limit": 5,
    "fields": "title,abstract,authors,year,publicationDate"
}
try:
    response = requests.get(url, params=params, timeout=10)
    data = response.json()
    print("Total:", data.get("total"))
    for p in data.get("data", []):
        print("-", p.get("title"))
except Exception as e:
    print("Error:", e)
