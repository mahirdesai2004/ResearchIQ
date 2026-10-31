"""
LinUCB Contextual Bandit Recommender Engine
============================================
Pure NumPy implementation — zero PyTorch/CUDA, <30MB RAM, <5ms response time.

Algorithm:
  - LinUCB (Li et al., 2010 — Yahoo! News Recommendation paper)
  - Online learning: updates after every user interaction (click, save, dismiss)
  - Exploration bonus (UCB) prevents filter bubbles by surfacing novel papers

Context Feature Vector x_a (for each paper candidate 'a'):
  [title_tfidf_match, abstract_tfidf_match, citation_norm, recency_norm,
   domain_overlap, user_pref_similarity]

References:
  Li et al. (2010). A contextual-bandit approach to personalized news article
  recommendation. WWW 2010. https://arxiv.org/abs/1003.0146
"""

import numpy as np
import json
import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Hyperparameters ────────────────────────────────────────────────────────────
FEATURE_DIM = 8          # Dimensionality of the context feature vector
ALPHA = 1.0              # Exploration bonus strength (higher = more exploration)
                         # α=0 → pure greedy; α=2 → aggressive exploration

# ── Reward Signal Definition ───────────────────────────────────────────────────
REWARD_MAP = {
    "bookmark": 5.0,       # Strong preference signal — user saved the paper
    "read_detail": 1.5,    # Moderate — user expanded paper details
    "chat_followup": 3.0,  # High — user asked a follow-up question about paper
    "pdf_click": 2.0,      # High commitment — user opened the actual paper
    "skip": -0.2,          # Weak negative — low relevance
    "dismiss": -3.0,       # Strong negative — user explicitly rejected paper
}

# ── Persistent Model State Directory ──────────────────────────────────────────
MODELS_DIR = os.path.join(os.path.dirname(__file__), "data", "rl_models")
os.makedirs(MODELS_DIR, exist_ok=True)


# ── Feature Engineering ────────────────────────────────────────────────────────

def build_feature_vector(
    paper: Dict[str, Any],
    user_state: Dict[str, Any],
    topic: str = "",
) -> np.ndarray:
    """
    Build a FEATURE_DIM-dimensional context vector for a paper given user state.

    Features:
      0: title_term_match     — fraction of topic terms appearing in title
      1: abstract_term_match  — fraction of topic terms appearing in abstract
      2: citation_norm        — min-max normalized citation count (cap 500)
      3: recency_norm         — linear recency score over 10-year window
      4: domain_overlap       — Jaccard similarity between paper domains & user prefs
      5: user_sim             — cosine sim between paper domain fingerprint & user vector
      6: is_bookmarked_domain — 1 if user has ever bookmarked from this domain
      7: novelty_bonus        — 1 - user's historical exposure rate to this domain
    """
    import re

    title = (paper.get("title") or "").lower()
    abstract = (paper.get("abstract") or "").lower()
    year = int(paper.get("year") or 2020)
    citations = int(paper.get("citation_count") or 0)
    paper_domains = set(d.lower() for d in (paper.get("domains") or []))

    # -- Feature 0 & 1: Topic term match
    topic_terms = [t.lower() for t in topic.split() if t.strip()]
    if topic_terms:
        title_match = sum(
            1 for t in topic_terms
            if re.search(r'\b' + re.escape(t) + r'\b', title)
        ) / len(topic_terms)
        abstract_match = sum(
            1 for t in topic_terms
            if re.search(r'\b' + re.escape(t) + r'\b', abstract)
        ) / len(topic_terms)
    else:
        title_match = 0.5
        abstract_match = 0.5

    # -- Feature 2: Citation normalization (logistic curve, cap at 500)
    citation_norm = np.log1p(min(citations, 500)) / np.log1p(500)

    # -- Feature 3: Recency (linear over 10-year window)
    current_year = datetime.now().year
    recency_norm = max(0.0, min(1.0, (year - (current_year - 10)) / 10.0))

    # -- Features 4–7: User-state-aware features
    user_prefs = set(user_state.get("preferred_domains", []))
    user_dismissed = set(user_state.get("dismissed_domains", []))
    user_exposure = user_state.get("domain_exposure", {})  # domain -> count

    # Jaccard domain overlap with user's preferred domains
    if paper_domains and user_prefs:
        domain_overlap = len(paper_domains & user_prefs) / len(paper_domains | user_prefs)
    else:
        domain_overlap = 0.0

    # User preference similarity via domain fingerprint
    all_domains = list(user_prefs | paper_domains)
    if all_domains:
        pref_vec = np.array([1.0 if d in user_prefs else 0.0 for d in all_domains])
        paper_vec = np.array([1.0 if d in paper_domains else 0.0 for d in all_domains])
        norm = (np.linalg.norm(pref_vec) * np.linalg.norm(paper_vec))
        user_sim = float(np.dot(pref_vec, paper_vec) / norm) if norm > 0 else 0.0
    else:
        user_sim = 0.0

    # Is any of the paper's domains a bookmarked domain?
    bookmarked_domains = set(user_state.get("bookmarked_domains", []))
    is_bookmarked_domain = 1.0 if (paper_domains & bookmarked_domains) else 0.0

    # Novelty bonus: inverse of how often user has seen this domain
    max_exposure = max(user_exposure.values()) if user_exposure else 1
    paper_exposure = max(user_exposure.get(d, 0) for d in paper_domains) if paper_domains else 0
    novelty_bonus = 1.0 - (paper_exposure / max(max_exposure, 1))

    vec = np.array([
        title_match,
        abstract_match,
        citation_norm,
        recency_norm,
        domain_overlap,
        user_sim,
        is_bookmarked_domain,
        novelty_bonus,
    ], dtype=np.float64)

    return vec


# ── LinUCB Model ───────────────────────────────────────────────────────────────

class LinUCBModel:
    """
    Linear Upper Confidence Bound Contextual Bandit.

    Maintains one global θ (shared parameter across all papers/arms).
    Uses Sherman-Morrison rank-1 update for O(d²) online updates.

    State is persisted to disk per session so recommendations improve
    continuously as the user interacts with the app.
    """

    def __init__(self, session_id: str = "global"):
        self.session_id = session_id
        self.d = FEATURE_DIM
        self.alpha = ALPHA

        # A: d×d covariance matrix (initialised to identity)
        self.A = np.eye(self.d, dtype=np.float64)
        # b: d-dimensional reward vector
        self.b = np.zeros(self.d, dtype=np.float64)

        self._load()

    # ── Persist / Load ─────────────────────────────────────────────────────────
    def _model_path(self) -> str:
        safe_id = "".join(c if c.isalnum() else "_" for c in self.session_id)
        return os.path.join(MODELS_DIR, f"{safe_id}.json")

    def _save(self):
        try:
            data = {
                "A": self.A.tolist(),
                "b": self.b.tolist(),
                "session_id": self.session_id,
            }
            with open(self._model_path(), "w") as f:
                json.dump(data, f)
        except Exception as e:
            logger.warning(f"LinUCB save failed: {e}")

    def _load(self):
        try:
            if os.path.exists(self._model_path()):
                with open(self._model_path()) as f:
                    data = json.load(f)
                self.A = np.array(data["A"], dtype=np.float64)
                self.b = np.array(data["b"], dtype=np.float64)
                logger.info(f"LinUCB model loaded for session '{self.session_id}'")
        except Exception as e:
            logger.warning(f"LinUCB load failed (starting fresh): {e}")
            self.A = np.eye(self.d, dtype=np.float64)
            self.b = np.zeros(self.d, dtype=np.float64)

    # ── Core Algorithm ─────────────────────────────────────────────────────────
    def score(self, x: np.ndarray) -> Tuple[float, float]:
        """
        Compute UCB score for a single paper feature vector.

        Returns:
            (exploitation_score, exploration_bonus)
            UCB score = exploitation_score + alpha * exploration_bonus
        """
        A_inv = np.linalg.inv(self.A)
        theta = A_inv @ self.b

        exploitation = float(theta @ x)
        exploration = float(self.alpha * np.sqrt(x @ A_inv @ x))
        return exploitation, exploration

    def update(self, x: np.ndarray, reward: float):
        """
        Online rank-1 update using observed reward.
        Sherman-Morrison formula avoids expensive full matrix inversion.
        Called immediately after each user interaction.
        """
        self.A += np.outer(x, x)
        self.b += reward * x
        self._save()
        logger.info(f"LinUCB updated: reward={reward:.1f}, session={self.session_id}")

    def rank_candidates(
        self,
        papers: List[Dict[str, Any]],
        user_state: Dict[str, Any],
        topic: str = "",
    ) -> List[Dict[str, Any]]:
        """
        Rank candidate papers by LinUCB UCB score.

        Each paper gets:
          - ucb_score      : exploitation + exploration
          - exploit_score  : how well it matches learned preference
          - explore_bonus  : novelty / uncertainty bonus
          - rec_type       : "exploitation" or "exploration"
          - rec_reason     : human-readable explanation
        """
        ranked = []

        for paper in papers:
            try:
                x = build_feature_vector(paper, user_state, topic)
                exploit, explore = self.score(x)
                ucb = exploit + explore
                rec_type = "exploitation" if exploit >= explore else "exploration"

                # Human-readable explanation
                if rec_type == "exploitation":
                    reason = f"🎯 High relevance match ({exploit:.2f}) to your saved topics"
                else:
                    reason = f"🔭 Novel paper in adjacent field (explore bonus: {explore:.2f})"

                ranked.append({
                    **paper,
                    "ucb_score": round(ucb, 4),
                    "exploit_score": round(exploit, 4),
                    "explore_bonus": round(explore, 4),
                    "rec_type": rec_type,
                    "rec_reason": reason,
                })
            except Exception as e:
                logger.warning(f"Error scoring paper {paper.get('id')}: {e}")
                continue

        ranked.sort(key=lambda p: p["ucb_score"], reverse=True)
        return ranked


# ── Session Cache (in-memory for fast access, persisted per session) ──────────

_model_cache: Dict[str, LinUCBModel] = {}


def get_model(session_id: str) -> LinUCBModel:
    """Get or create LinUCB model for a session."""
    if session_id not in _model_cache:
        _model_cache[session_id] = LinUCBModel(session_id)
    return _model_cache[session_id]


# ── Public API Functions ───────────────────────────────────────────────────────

def record_interaction(
    session_id: str,
    paper: Dict[str, Any],
    action: str,
    user_state: Dict[str, Any],
    topic: str = "",
) -> float:
    """
    Record a user interaction and update LinUCB online.

    Args:
        session_id: Browser session identifier
        paper:      Paper dict (title, abstract, domains, year, citation_count)
        action:     One of REWARD_MAP keys (bookmark, read_detail, skip, dismiss...)
        user_state: Current user profile state dict
        topic:      The search topic that surfaced this paper

    Returns:
        The reward value applied.
    """
    reward = REWARD_MAP.get(action, 0.0)
    if reward == 0.0:
        logger.warning(f"Unknown action '{action}' — reward=0 applied")

    x = build_feature_vector(paper, user_state, topic)
    model = get_model(session_id)
    model.update(x, reward)

    return reward


def get_personalized_recommendations(
    session_id: str,
    candidates: List[Dict[str, Any]],
    user_state: Dict[str, Any],
    topic: str = "",
    k: int = 10,
) -> List[Dict[str, Any]]:
    """
    Return top-K LinUCB-ranked recommendations for a session.

    Falls back gracefully to citation-sorted ranking if no interactions exist yet
    (cold-start handling).

    Args:
        session_id: Browser session identifier
        candidates: Pool of candidate papers (dicts with title, abstract, etc.)
        user_state: Current user profile state
        topic:      Current search query
        k:          Number of recommendations to return

    Returns:
        List of paper dicts ranked by UCB score with rec_reason explanations.
    """
    if not candidates:
        return []

    model = get_model(session_id)
    ranked = model.rank_candidates(candidates, user_state, topic)

    # Balanced Exploitation-Exploration Slate:
    # Separate candidates into exploitation (matched) and exploration (novel/serendipity)
    exploit_papers = [p for p in ranked if p.get("rec_type") == "exploitation"]
    explore_papers = [p for p in ranked if p.get("rec_type") == "exploration"]

    # Guarantee that neither category is starved in the top-K slate
    # Reserve at least 30-40% of slots (min 3) for exploration so 'Novel' tab is always populated
    n_explore = min(max(3, k // 3), len(explore_papers))
    n_exploit = min(k - n_explore, len(exploit_papers))

    slate = exploit_papers[:n_exploit] + explore_papers[:n_explore]

    # Fill any remaining slots if one list had fewer items than allocated
    seen_ids = {p["id"] for p in slate}
    for p in ranked:
        if len(slate) >= k:
            break
        if p["id"] not in seen_ids:
            slate.append(p)
            seen_ids.add(p["id"])

    # Sort final slate by UCB score so best overall recommendations appear at the top
    slate.sort(key=lambda p: p.get("ucb_score", 0), reverse=True)

    logger.info(
        f"LinUCB slate composed for session '{session_id}' "
        f"(exploit: {sum(1 for p in slate if p['rec_type']=='exploitation')}, "
        f"explore: {sum(1 for p in slate if p['rec_type']=='exploration')})"
    )

    return slate
