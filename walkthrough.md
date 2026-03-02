# ResearchIQ - Comprehensive Project Walkthrough

## Executive Summary
ResearchIQ is an LLM-based research analytics system. It acts as a lightweight, fast, and extensible backend service that ingests research papers from arXiv, stores them intelligently, provides robust filtering analytics, and uses AI (Google Gemini 2.5) to synthesize their abstracts into core scientific takeaways.

The backend is entirely developed in **Python (3.12+)** using **FastAPI** as the routing engine and **uv** as the ultra-fast dependency manager.

---

## Phase 1: Foundation & Data Ingestion
**Goal**: Build a solid backbone for the API and ingest real-world research data.

1. **Setup**: We scaffolded the project with FastAPI (`backend/main.py`) which gives us auto-generating OpenAPI docs right out of the box. We used `uv` to manage our dependencies tightly via `pyproject.toml`.
2. **Ingestion Engine**: We implemented the `GET /papers/arxiv` endpoint. It accepts a `query` (e.g., "Generative AI") and hits the public arXiv API.
3. **Data Normalization**: arXiv sends back XML. We parse this XML using Python's `xml.etree.ElementTree`, abstracting title, abstract, and published year.
4. **Persistence & Deduplication**: Instead of jumping straight to a heavy database, we used a flat JSON file (`backend/data/papers.json`). Whenever new papers are pulled, the system checks for existing titles and only appends unique entries, preventing data duplication.

---

## Phase 2: Analytics Data Layer
**Goal**: Query the ingested papers and perform quantitative analyses.

1. **Data Load Safety**: We abstracted the JSON loading and saving logic into `backend/utils.py`. The loaders now gracefully handle missing files or broken JSON.
2. **Aggregation (`GET /analytics/yearly-count`)**: Computes how many papers were published each year based on our local dataset.
3. **Filtering (`GET /analytics/filter`)**: A semantic pipeline that allows case-insensitive filtering based on `year` or `keyword` string-matching against both the title and the abstract.

---

## Phase 3: The Intelligence Layer (LLM Integration)
**Goal**: Take unstructured data (abstracts) and synthesize actionable intelligence.

1. **Summarization (`GET /analytics/summaries`)**:
   - We connected the backend to Google's **Gemini 2.5 Flash** (with fallback to **Gemini 2.5 Pro**).
   - This endpoint iterates over our dataset. If a paper lacks a "summary" field, it dynamically shoots the abstract to the LLM to extract the core 2-3 sentence contribution.
   - **Performance Caching**: Once the LLM returns a summary, it is saved back into the `papers.json` record permanently so it never hits the LLM for that paper again.
2. **Trend Analysis (`GET /analytics/keyword-trend`)**:
   - An endpoint that searches for a specific `keyword` (e.g., "AI", "Agent") and builds a histogram of how frequently that word appears across publication years.

---

## Phase 3.5: Enterprise Maturity & Architecture Upgrade
**Goal**: Prepare the system for production resilience, clean up the architecture, and validate all behaviors.

1. **Project Restructuring**: We created clean separation of concerns by adding a `docs/` folder (for `architecture.md`) and a `scripts/` folder for our testing scripts.
2. **Pydantic Validation Pipeline**: All ingested and loaded data now passes strictly through a Pydantic `Paper` schema inside `utils.py`. If a corrupted paper enters the stream via manual tampering, it is safely dropped rather than crashing the API endpoints.
3. **More Analytics**:
   - `GET /system/stats`: Returns macroscopic numbers like total papers and bounds (earliest/latest dataset year).
   - `GET /analytics/recent-papers`: Sorts the data array mathematically by year descending and returns the latest drops.
   - `GET /analytics/top-keywords`: A custom tokenization pipeline that strips common English stop-words ("the", "and") and returns the highest-frequency semantic keywords appearing across all paper titles.
4. **Resilient LLM Key Rotation System**:
   - The Gemini integration was upgraded to handle enterprise rate-limiting. A comma-separated list of `GEMINI_API_KEYS` is loaded from a hidden `.env` file via `dotenv`. 
   - If a key fails (Quota Exhausted, 429 Error), the engine automatically rotates to the next API key in the environmental array and re-attempts the generation, ensuring uninterrupted scaling.
5. **Testing & Logging**: Comprehensive `try/except` blocks injected across all routes with detailed `logger` integrations. Every endpoint was tested successfully via our script `scripts/verify_analytics.py`.

---

## Future Trajectory (Phase 4+)
The foundation is now perfect for full Retrieval-Augmented Generation (RAG). The next logical step is migrating `papers.json` to an abstraction layer holding a Vector Database (like Pinecone or ChromaDB), running semantic embeddings on the abstracts, and creating a QA `/analytics/chat` endpoint.
