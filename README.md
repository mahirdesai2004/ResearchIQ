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

## Project Structure

```
.
├── README.md           # This file
├── backend/
│   ├── data/           # Local data storage
│   │   └── papers.json # Saved paper metadata
│   ├── main.py         # Main application and endpoints
│   ├── pyproject.toml  # Project configuration and dependencies
│   └── uv.lock         # Dependency lock file
```
