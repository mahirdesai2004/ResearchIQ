import os
from datetime import datetime
from sqlalchemy import create_engine, Column, String, Text, Integer, JSON, DateTime, Date, text
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
    published = Column(Date, nullable=True)
    year = Column(Integer, index=True, nullable=False)
    source = Column(String, default="arxiv", nullable=False)
    domains = Column(JSON, nullable=False, index=True)
    keywords = Column(JSON, nullable=False, index=True)
    summary = Column(Text, nullable=True)
    url = Column(String, nullable=True)
    pdf_url = Column(String, nullable=True)
    citation_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserInteraction(Base):
    __tablename__ = "user_interactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, index=True, nullable=False)
    paper_id = Column(String, index=True, nullable=False)
    action = Column(String, nullable=False) # bookmark, read_detail, chat_followup, pdf_click, dismiss
    reward = Column(Integer, default=0)
    topic = Column(String, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

class UserSessionProfile(Base):
    __tablename__ = "user_session_profiles"

    session_id = Column(String, primary_key=True, index=True)
    preferred_domains = Column(JSON, default=list)
    bookmarked_domains = Column(JSON, default=list)
    dismissed_domains = Column(JSON, default=list)
    domain_exposure = Column(JSON, default=dict)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create tables
Base.metadata.create_all(bind=engine)

# Migration: add citation_count column if missing (for existing DBs)
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE papers ADD COLUMN citation_count INTEGER DEFAULT 0"))
        conn.commit()
except Exception:
    pass  # Column already exists

# Migration: add url columns
try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE papers ADD COLUMN url VARCHAR"))
        conn.commit()
except Exception:
    pass

try:
    with engine.connect() as conn:
        conn.execute(text("ALTER TABLE papers ADD COLUMN pdf_url VARCHAR"))
        conn.commit()
except Exception:
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
