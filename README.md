# 🧠 ResearchIQ: Smart Research Paper Recommendation System

> **Personalized Academic Paper Recommendations using LinUCB Contextual Bandits**  
> *Under the Guidance of **Dr. Neelam Chaplot** | Department of Computer Science & Engineering, Manipal University Jaipur*  
> *Developed by **Mahir Desai** (23FE10CSE00345) & **Nemat Sachdeva** (23FE10CSE00107)*

---

## 📌 Project Links & Video Demonstration

| Resource | Link |
| :--- | :--- |
| 🌐 **Live Web Application (Vercel)** | [https://research-iq-seven.vercel.app/](https://research-iq-seven.vercel.app/) |
| 🎥 **Project Video Demonstration** | [Google Drive Video Demo](https://drive.google.com/file/d/1S3cl5CNLWIA592QjOoHWrzxc8G1Kpg51/view?usp=sharing) |
| 💻 **GitHub Source Code** | [https://github.com/mahirdesai2004/ResearchIQ](https://github.com/mahirdesai2004/ResearchIQ) |
| 📄 **Full Academic Research Report** | [`23FE10CSE00345_Mahir_Desai_project.pdf`](./docs/main.pdf) |

---

## 🔬 How the Recommender System Works (Evaluation Guide)

Standard search engines only look at keywords and static citation counts. They fail newly published papers (Cold-Start Problem) and trap users in identical results (Filter Bubbles).

**ResearchIQ** treats academic paper recommendation as an **Online Reinforcement Learning (Contextual Bandit)** problem powered by the **LinUCB** algorithm.

### 🧪 Step-by-Step Instructions to Test the Live System

1. **Open the Live Application:**  
   Navigate to [https://research-iq-seven.vercel.app/](https://research-iq-seven.vercel.app/) (or run locally at `http://localhost:5173`).
2. **Initial Search (Cold-Start Phase):**  
   Enter an initial broad research query, such as:  
   `"deep reinforcement"` or `"vt vf"`.  
   > **Note on Cold-Start:** On the very first search of a new session, your preference vector is uninitialized ($\mathbf{b} = \mathbf{0}$). The system serves an exploratory candidate slate. You will see candidate literature while the bandit waits for your feedback.
3. **Train the Agent (Explicit & Implicit Interactions):**  
   - Click **`Save` (Bookmark)** on 1–2 papers that match your research interest (awards **$+5.0$ reward**).
   - Click **`PDF`** to view full text (awards **$+2.0$ reward**).
   - Click **`Dismiss` (Thumbs Down)** on any irrelevant paper (applies **$-3.0$ penalty**).
4. **Observe Real-Time Dynamic Re-ranking:**  
   - Enter a related query (e.g. search for an adjacent subfield), or hit the **Refresh** button on the **"Recommended for You"** feed.
   - The LinUCB agent updates immediately in **$< 0.4$ ms** using the **Sherman-Morrison rank-1 matrix update**.
5. **Inspect the Two-Sided Slate Tabs:**  
   - **`All`**: Displays the balanced personalized slate ranked by Upper Confidence Bound ($UCB$) score.
   - **`🎯 Matched` (Exploitation)**: Surfaces papers directly aligned with your saved topics and bookmark fingerprints.
   - **`✨ Novel` (Exploration)**: Surfaces high-uncertainty papers from adjacent research fields to break filter bubbles and introduce serendipitous discoveries.

---

## ⚙️ Mathematical Formulation: LinUCB Contextual Bandit

For each candidate paper $a$ characterized by feature context $\mathbf{x}_{t,a} \in \mathbb{R}^8$:

$$\text{UCB}_{t,a} = \underbrace{\hat{\boldsymbol{\theta}}_t^\top \mathbf{x}_{t,a}}_{\text{Exploitation (Learned Preference)}} + \underbrace{\alpha \sqrt{\mathbf{x}_{t,a}^\top \mathbf{A}_t^{-1} \mathbf{x}_{t,a}}}_{\text{Exploration (Confidence / Novelty Bonus)}}$$

where:
- $\mathbf{A}_t = \mathbf{I}_d + \sum_{\tau=1}^{t-1} \mathbf{x}_\tau \mathbf{x}_\tau^\top \in \mathbb{R}^{8 \times 8}$ is the covariance matrix.
- $\mathbf{b}_t = \sum_{\tau=1}^{t-1} r_\tau \mathbf{x}_\tau \in \mathbb{R}^8$ is the accumulated reward vector.
- $\hat{\boldsymbol{\theta}}_t = \mathbf{A}_t^{-1} \mathbf{b}_t$ is the ridge-regression weight estimate of user interest.
- Online update via **Sherman-Morrison formula**:
  $$\mathbf{A}_{t+1}^{-1} = \mathbf{A}_t^{-1} - \frac{\mathbf{A}_t^{-1} \mathbf{x}_t \mathbf{x}_t^\top \mathbf{A}_t^{-1}}{1 + \mathbf{x}_t^\top \mathbf{A}_t^{-1} \mathbf{x}_t}$$

### Contextual Feature Vector $\mathbf{x} \in \mathbb{R}^8$
1. Title keyword overlap ($[0, 1]$)
2. Abstract BM25 similarity ($[0, 1]$)
3. Normalized citation impact ($\log(1 + c) / \log(501)$)
4. Recency factor (linear 10-year window)
5. Jaccard domain overlap with bookmarked domains
6. Cosine similarity to user profile domain fingerprint
7. Bookmarked domain indicator ($\{0, 1\}$)
8. Domain novelty bonus ($1 - \text{exposure} / \max(\text{exposure})$)

---

## 📊 Benchmark Results

Evaluated across 100 interaction steps on a corpus of 243 real research papers across 5 domains (Reinforcement Learning, NLP, Healthcare ML, Computer Vision, Cybersecurity):

| Metric | Random Baseline | Citation Popularity | Static BM25 | **LinUCB (Ours)** | Improvement |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Precision@5** | 0.20 | 0.40 | 0.60 | **1.00** | $+150\%$ vs Citations |
| **Precision@10** | 0.20 | 0.30 | 0.50 | **1.00** | $+233\%$ vs Citations |
| **NDCG@10** | 0.21 | 0.30 | 0.52 | **1.00** | $+233\%$ vs Citations |
| **Online Latency** | $0.05\,\text{ms}$ | $0.21\,\text{ms}$ | $2.10\,\text{ms}$ | **$0.38\,\text{ms}$** | Real-time interactive |

---

## 🛠️ Local Development Setup

### 1. Clone the Repository
```bash
git clone https://github.com/mahirdesai2004/ResearchIQ.git
cd ResearchIQ
```

### 2. Backend Setup (FastAPI / Python 3.12)
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --port 8000 --host 0.0.0.0 --reload
```
*Backend runs on `http://localhost:8000` with interactive API docs at `http://localhost:8000/docs`.*

### 3. Frontend Setup (React / Vite / Tailwind)
```bash
cd frontend
npm install
npm run dev
```
*Frontend runs on `http://localhost:5173`.*

---

## 👥 Authors & Academic Affiliation

* **Mahir Desai** — Registration No: `23FE10CSE00345` (Section C)
* **Nemat Sachdeva** — Registration No: `23FE10CSE00107` (Section C)
* **Project Guide:** Dr. Neelam Chaplot
* **Department:** Department of Computer Science and Engineering  
* **Institution:** Manipal University Jaipur, Rajasthan, India
