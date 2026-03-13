import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, Integer, JSON, DateTime, Date
from sqlalchemy.orm import declarative_base, sessionmaker

# Ensure data directory exists
os.makedirs("data", exist_ok=True)

SQLALCHEMY_DATABASE_URL = "sqlite:///./data/papers.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class PaperModel(Base):
    __tablename__ = "papers"

    id = Column(String, primary_key=True, index=True)
    title = Column(Text, nullable=False)
    abstract = Column(Text, nullable=False)
    authors = Column(JSON, nullable=False)
    published = Column(Date, nullable=False)
    year = Column(Integer, index=True, nullable=False)
    source = Column(String, default="arxiv", nullable=False)
    domains = Column(JSON, nullable=False, index=True)
    keywords = Column(JSON, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
