# ResearchIQ Backend

Backend service for **ResearchIQ**, an LLM-based research analytics system. This service handles data ingestion, API routing, and future LLM/RAG operations.

## Tech Stack

*   **Framework:** FastAPI
*   **Language:** Python 3.12+
*   **Dependency Management:** [uv](https://github.com/astral-sh/uv)
*   **Data Source:** arXiv API
*   **LLM Integration:** Google Gemini (2.5 Flash/Pro) via `google-genai`

## Architecture
The system has been transformed into a structured analytics pipeline. It uses batch ingestion to fetch and tag papers by domain, extracts key topics, and serves analytical insights (trends, stats) over the static dataset without real-time delays. See [docs/architecture.md](docs/architecture.md) for a detailed overview.

## Setup & Installation

1.  **Install uv** (if not installed):
    ```bash
    curl -LsSf https://astral.sh/uv/install.sh | sh
    ```

2.  **Install Dependencies**:
    ```bash
    cd backend
    uv sync
    ```

3.  **Environment Variables**:
    Create a `.env` file in the `backend/` directory by copying from the example:
    ```bash
    cp .env.example .env
    ```
    Then, populate `GEMINI_API_KEYS` in `.env`.
    *Note: API keys are strictly loaded from `.env` and multiple keys can be provided as a comma-separated string for rate-limit rotation. For security, never commit real API keys into the repository. `.env` is ignored by git.*

4.  **Run Development Server**:
    ```bash
    uv run uvicorn main:app --reload
    ```
    The server will start at `http://127.0.0.1:8000`.

## API Endpoints

### 1. Health Check
*   **URL:** `GET /`
*   **Description:** Returns a welcome message to verify the API is running.

### 2. Search ArXiv Papers
*   **URL:** `GET /papers/arxiv`
*   **Parameters:**
    *   `query` (string, default: "ai"): The search term.
    *   `max_results` (int, default: 50): Number of papers to fetch.
*   **Description:** Fetches papers from the arXiv API, tags their domain, deduplicates them, and appends them to `data/papers.json`.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/papers/arxiv?query=generative+ai&max_results=50"
    ```

### 3. Batch Ingest ArXiv Papers
*   **URL:** `POST /papers/arxiv/batch`
*   **Description:** Fetches 50 papers for several predefined key topics (AI, ML, LLM, NLP, CV), tags their domains, and deduplicates them.
*   **Example:**
    ```bash
    curl -X POST "http://127.0.0.1:8000/papers/arxiv/batch"
    ```

### 3. Analytics: Yearly Count
*   **URL:** `GET /analytics/yearly-count`
*   **Description:** Aggregates stored papers by their published year.
*   **Returns:** JSON object with years as keys and paper counts as values.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/analytics/yearly-count"
    ```

### 4. Analytics: Filter Papers
*   **URL:** `GET /analytics/filter`
*   **Parameters:**
    *   `year` (string, optional): Filter by published year.
    *   `keyword` (string, optional): Case-insensitive search in title and abstract.
*   **Description:** Filters stored papers based on year and/or keyword.
*   **Example:**
    ```bash
    # Filter by year
    curl "http://127.0.0.1:8000/analytics/filter?year=2023"

    # Filter by keyword
    curl "http://127.0.0.1:8000/analytics/filter?keyword=agent"
    ```

### 5. Analytics: Summaries
*   **URL:** `GET /analytics/summaries`
*   **Description:** Returns stored papers with an LLM-ready summary generated from their abstracts. Summaries are cached for performance.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/analytics/summaries"
    ```

### 6. Analytics: Keyword Trend
*   **URL:** `GET /analytics/keyword-trend`
*   **Parameters:**
    *   `keyword` (string, required): The keyword to track trends for in titles and abstracts.
*   **Description:** Analyzes the frequency of a specific keyword across publication years.
*   **Returns:** JSON object with the keyword and a dictionary of yearly counts.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/analytics/keyword-trend?keyword=ai"
    ```

### 7. System: Stats
*   **URL:** `GET /system/stats`
*   **Description:** Returns high-level statistics about the stored research dataset.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/system/stats"
    ```

### 8. Analytics: Recent Papers
*   **URL:** `GET /analytics/recent-papers`
*   **Parameters:** `limit` (int, default: 10)
*   **Description:** Returns the most recent papers sorted by published year descending.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/analytics/recent-papers?limit=5"
    ```

### 10. Analytics: Top Keywords
*   **URL:** `GET /analytics/top-keywords`
*   **Parameters:**
    *   `limit` (int, default: 10): Number of keywords.
    *   `min_length` (int, default: 3): Minimum string length of a keyword.
*   **Description:** Computes the most frequent keywords appearing in the titles of stored papers, discounting common stop words.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/analytics/top-keywords?limit=5"
    ```

### 11. Analytics: Domain Trends
*   **URL:** `GET /analytics/domain-trends`
*   **Parameters:**
    *   `domain` (string, required): Domain to track trends for (e.g., "ML").
*   **Description:** Returns the yearly publication trend for a specific domain based on the tagged dataset.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/analytics/domain-trends?domain=ML"
    ```

### 12. Export: Tableau Data
*   **URL:** `GET /export/tableau-data`
*   **Description:** Exports the stored papers in CSV format suitable for ingestion into Tableau.
*   **Example:**
    ```bash
    curl -O -J "http://127.0.0.1:8000/export/tableau-data"
    ```

## Project Structure

```
.
├── README.md           # This file
├── backend/            # API Core and Utils
│   ├── data/           # Local data storage (papers.json)
│   ├── main.py         # Main application and endpoints
│   ├── utils.py        # Helper functions and dataset validation
│   ├── pyproject.toml  # Project configuration and dependencies
│   └── uv.lock         # Dependency lock file
├── docs/               # System architecture and documentation
│   └── architecture.md
└── scripts/            # Verification scripts
    └── verify_analytics.py
```
