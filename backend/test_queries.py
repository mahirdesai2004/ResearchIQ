import requests

def test_query(topic):
    print(f"\n--- Testing: {topic} ---")
    try:
        res = requests.post('http://127.0.0.1:8000/research/query', json={'topic': topic, 'purpose': 'deep dive', 'num_papers': 10})
        res.raise_for_status()
        data = res.json()
        
        print("QUERY PARSED:", data.get('parsed_query', {}))
        
        papers = data.get('papers', [])
        print(f"Returned {len(papers)} papers")
        for i, p in enumerate(papers):
            print(f"{i+1}. {p['title']}")
            print(f"   Score: {p.get('score', 0)}% - Reason: {p.get('llm_reason')}")
    except Exception as e:
        print("Error:", e, res.text if 'res' in locals() else '')

if __name__ == "__main__":
    test_query("parkinson eeg detection")
    test_query("nlp transformers")
