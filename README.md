# ResearchIQ 🚀

![ResearchIQ Dynamic Dashboard](https://img.shields.io/badge/ResearchIQ-AI_Powered_Analytics-f97316?style=for-the-badge&logoColor=white)
![React](https://img.shields.io/badge/React-18.x-61dafb?style=for-the-badge&logo=react)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi)
![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite)

ResearchIQ is a next-generation, context‑aware AI research assistant. It solves the fragmentation of academic literature by dynamically aggregating papers across multiple global registries (Semantic Scholar, OpenAlex, CrossRef, arXiv), synthesizing the data with LLMs, and projecting the insights onto a stunning, real-time interactive dashboard.

### 🌟 Key Features
- **Zero-Empty Multi-Source Waterfall**: Guarantees results for any query by cascading through semantic graphs and DOI registries until dataset quotas are met.
- **AI Executive Summaries**: Distills dense academic abstracts into cohesive paragraphs using Google Gemini (with Mistral/OpenRouter graceful fallbacks).
- **Sentence-Form Gap Detection**: Analyzes cross-domain vectors to write full sentences identifying exactly where research is lacking (temporal, methodological, sub-topical).
- **Interactive Visual Analytics**: Fully bespoke React components charting publication trends, source distributions, and dynamic correlation metrics.
- **Glassmorphic Fluid UI**: Engineered with an `Orange/Purple/Rose` primary palette featuring custom `@keyframes` physics, floating cards, and a real-time responsive Canvas2D particle environment.

---

## 🛠️ Project Setup & Installation

Follow these steps to run the full stack locally. You need `Node.js` (for the frontend) and `Python 3.10+` (for the backend).

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/ResearchIQ.git
cd ResearchIQ
```

### 2. Backend Setup (FastAPI & SQLite)
The backend manages the data ingestion, database caching, dynamic relevance filtering, and API cascading.

```bash
cd backend

# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure Environment Variables
# Create a .env file and add your AI keys
echo "GEMINI_API_KEYS=your_google_ai_studio_key" > .env
echo "OPENROUTER_API_KEY=your_openrouter_free_key_optional" >> .env

# Run the API server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
*Note: The `papers.db` database will automatically initialize in the `data/` folder on first run.*

### 3. Frontend Setup (React & Vite)
The front-end is a high-performance, purely functional UI leveraging Tailwind CSS for deep bespoke styling.

```bash
# Open a new terminal window
cd frontend

# Install dependencies
npm install

# Start the Vite development server
npm run dev
```
Navigate to **`http://localhost:5173`** to access the ResearchIQ dashboard!

---

## 🏗️ Architecture & Core Endpoints

### The "Zero-Failure" Intelligent Query
**`POST /research/query`**
Executes the deep-search algorithm. Returns papers, charts, LLM summaries, and keyword gaps.
```bash
curl -X POST http://127.0.0.1:8000/research/query \
     -H "Content-Type: application/json" \
     -d '{"topic": "protein coagulation", "purpose": "deep dive", "num_papers": 10}'
```

### Purpose Engine Responses
| Purpose Option | AI Orchestration Output |
| :--- | :--- |
| **`literature review`** | Synthesizes a structured historical transition of the topic's development. |
| **`quick overview`** | Rapidly extracts the 4 most critical findings without hallucination. |
| **`deep dive`** | Cross-correlates raw data, pulling top citations and executing domain gap mapping. |

### Tableau Data Hoses
For BI professionals, ResearchIQ seamlessly streams its SQL cache into CSV formatting:
- `GET /export/tableau-data` (Raw Paper Data)
- `GET /export/tableau-aggregates` (Grouped Time-Series)

---
*Built to cut research literature review duration by 75%.*
