import requests

query_payload = {"topic": "machine learning", "purpose": "deep dive", "num_papers": 5}
r = requests.post("http://localhost:8000/research/query", json=query_payload)
data = r.json()
pids = [p["id"] for p in data["papers"]]

print("Papers found:", len(pids))
analysis_payload = {"topic": "machine learning", "purpose": "deep dive", "paper_ids": pids}
r2 = requests.post("http://localhost:8000/analytics/analysis", json=analysis_payload)
print(r2.json())
