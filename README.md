# ResearchIQ Backend (SQLAlchemy Edition)

ResearchIQ is a context‑aware, LLM‑based research analytics system. It ingests scientific papers directly from the arXiv API into a local SQLite database, extracts keywords, tags domains, applies relevance ranking, and provides purpose-tailored insights (like literature reviews, quick overviews, and deep dives). It also supports CSV streaming for Tableau integration.

## Setup Instructions

1. **Clone the repository and enter the backend directory**
2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Configure the Environment:**
   Set your Google Gemini API key to enable LLM summaries. In `backend/.env`, add:
   ```
   GEMINI_API_KEYS=your_api_key_here
   ```
4. **Run the API server:**
   ```bash
   uvicorn main:app --reload
   ```
   The backend will be available at [http://127.0.0.1:8000](http://127.0.0.1:8000). The database (`papers.db`) will be automatically created in the `data/` directory.

## Endpoints

### Context-Aware Query
**POST `/research/query`**
Generates tailored responses based on your reading purpose.
```bash
curl -X POST http://127.0.0.1:8000/research/query \
     -H "Content-Type: application/json" \
     -d '{"topic": "machine learning", "purpose": "literature review", "num_papers": 10}'
```

| Purpose | Behavior |
| :--- | :--- |
| `literature review` | Diversifies results temporally (round-robin across years). |
| `quick overview` | Takes top 5 relevant papers and generates LLM summaries. |
| `deep dive` | Returns all requested papers and extracts top 10 related keywords across the batch. |

### Tableau Export
**GET `/export/tableau-data`**
Streams a CSV of stored papers for direct import into Tableau. Optional query params: `domain`, `year_min`, `year_max`.
```bash
curl -O -J http://127.0.0.1:8000/export/tableau-data
```

### Batch Ingestion
**POST `/papers/arxiv/batch`**
Triggers a background ingestion of massive topics (AI, ML, NLP, LLM, CV). Fetches 100 recent papers per domain.
```bash
curl -X POST http://127.0.0.1:8000/papers/arxiv/batch
```

### Existing Analytics
- `GET /analytics/filter`: Flexible filtering by `q`, `year_min`, `year_max`, `domains`.
- `GET /analytics/yearly-count`: Count of papers grouped by publication year.
- `GET /analytics/keyword-trend`: Track keyword usage across years.
