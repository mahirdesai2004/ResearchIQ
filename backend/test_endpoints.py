from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_arxiv():
    response = client.get("/papers/arxiv?query=llm&max_results=5")
    print("arxiv:", response.status_code, response.json().get('count', response.json()))

def test_stats():
    response = client.get("/system/stats")
    print("stats:", response.status_code, response.json())

def test_filter():
    response = client.get("/analytics/filter?limit=2&offset=0")
    print("filter:", response.status_code, response.json().get('returned'))

test_arxiv()
test_stats()
test_filter()
