import sys
import logging
from sqlalchemy.orm import Session
from main import research_query, ResearchQuery
from database import SessionLocal

logging.basicConfig(level=logging.INFO)

db = SessionLocal()
req = ResearchQuery(topic="machine learning", purpose="deep dive", num_papers=20)

try:
    print("Testing research_query endpoint logic...")
    result = research_query(req, db)
    print("Result keys:", result.keys())
    print("Papers found:", len(result.get("papers", [])))
except Exception as e:
    import traceback
    traceback.print_exc()

db.close()
