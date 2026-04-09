# 🧠 ResearchIQ

> A Zero-Failure AI-Powered Research Assistant

![ResearchIQ Demo](frontend_landing.png) <!-- Update image path if needed -->

ResearchIQ transforms how researchers conduct literature reviews by instantly aggregating papers, extracting methodologies, and mapping explicit research gaps over massive datasets unconditionally.

## ✨ Features
- **Zero-Failure Architecture:** 3-layer deep fallback logic guarantees zero dead APIs. (Gemini → OpenRouter → Local LLM Defaults)
- **Deep Academic Aggregation:** Cascades seamlessly through Semantic Scholar, OpenAlex, and CrossRef.
- **Dynamic Research Gaps:** Autonomously calculates gaps in current methodologies into comprehensive textual checklists.
- **Interactive Publications Timeline:** Fully resilient analytic visualizers providing trends on topics over decades.
- **PDF Extraction Guarantee:** Native source-aware link generation safely binds direct PDF targets across 3 separate academic database standards natively.

## 🚀 Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/your-username/ResearchIQ.git
cd ResearchIQ
```

### 2. Frontend Setup (React / Vite)
```bash
cd frontend
npm install
npm run dev
```
*Frontend will run locally on `http://localhost:5173`*

### 3. Backend Setup (FastAPI / Python)
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```
*Backend will run locally on `http://localhost:8000`*

### 4. Keys & Configurations (Optional)
Make a duplicate of the `.env.example` in `/backend` to `.env`.
```
GEMINI_API_KEYS=your_first_gemini_key,your_second_gemini_key
S2_API_KEYS=your_semanticscholar_key
```

## 🏗️ Architecture
ResearchIQ implements a deterministic failsafe layout:
- **UI Degradation Protection:** If historical graphs collapse, base visualizers invoke standard analytic boundaries.
- **Dynamic Dataset Tokenization:** Automatically restricts or expands semantic keyword mapping based on precise context limits.
- **Chatbot Resiliency:** Encased entirely inside exception fallbacks, meaning local queries never cascade internal python runtime errors onto the interface.

## 📝 License
This project is officially licensed under the MIT License - see the [LICENSE](LICENSE) file for more information.
