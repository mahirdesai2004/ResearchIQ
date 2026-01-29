# ResearchIQ Backend

Backend service for **ResearchIQ**, an LLM-based research analytics system. This service handles data ingestion, API routing, and future LLM/RAG operations.

## Tech Stack

*   **Framework:** FastAPI
*   **Language:** Python 3.12+
*   **Dependency Management:** [uv](https://github.com/astral-sh/uv)
*   **Data Source:** arXiv API

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

3.  **Run Development Server**:
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
    *   `max_results` (int, default: 5): Number of papers to fetch.
*   **Description:** Fetches papers from the arXiv API and appends them to `data/papers.json`.
*   **Example:**
    ```bash
    curl "http://127.0.0.1:8000/papers/arxiv?query=generative+ai&max_results=3"
    ```

## Project Structure

```
backend/
├── data/               # Local data storage
│   └── papers.json     # Saved paper metadata
├── main.py             # Main application and endpoints
├── pyproject.toml      # Project configuration and dependencies
├── uv.lock             # Dependency lock file
└── README.md           # This file
```
