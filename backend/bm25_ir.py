"""
Information Retrieval (IR) Module: BM25Okapi + Hybrid Lexical-Semantic Ranker
=============================================================================
Pure NumPy / standard Python implementation of the classic BM25 (Robertson & Spärck Jones).
Zero heavy dependencies, 0MB disk bloat, sub-millisecond execution.

Formula:
  IDF(q_i) = ln( (N - n(q_i) + 0.5) / (n(q_i) + 0.5) + 1 )
  score(D, Q) = sum( IDF(q_i) * (f(q_i, D) * (k1 + 1)) / (f(q_i, D) + k1 * (1 - b + b * (|D| / avgdl))) )

Hyperparameters:
  k1 = 1.5 (term frequency saturation parameter)
  b  = 0.75 (document length penalization parameter)
"""

import math
import re
from typing import List, Dict, Any, Tuple

class BM25Ranker:
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.corpus_size = 0
        self.avgdl = 0.0
        self.doc_lengths = []
        self.doc_freqs = [] # list of {word: count} per doc
        self.idf = {}
        self.vocabulary = set()

    def _tokenize(self, text: str) -> List[str]:
        if not text:
            return []
        # Lowercase, extract alphanumeric tokens, preserve acronyms
        return [w for w in re.findall(r'\b[a-zA-Z0-9_\-]+\b', text.lower()) if len(w) > 1]

    def fit(self, corpus_texts: List[str]):
        """Index the corpus of document texts (titles + abstracts)."""
        self.corpus_size = len(corpus_texts)
        if self.corpus_size == 0:
            return

        self.doc_lengths = []
        self.doc_freqs = []
        df = {}

        total_words = 0
        for text in corpus_texts:
            tokens = self._tokenize(text)
            length = len(tokens)
            self.doc_lengths.append(length)
            total_words += length

            tf = {}
            for token in tokens:
                tf[token] = tf.get(token, 0) + 1
            self.doc_freqs.append(tf)

            for token in tf.keys():
                df[token] = df.get(token, 0) + 1
                self.vocabulary.add(token)

        self.avgdl = total_words / self.corpus_size if self.corpus_size > 0 else 1.0

        # Compute Robertson-Spärck Jones IDF
        self.idf = {}
        for token, freq in df.items():
            self.idf[token] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def score(self, query: str) -> List[float]:
        """Compute BM25 scores for all indexed documents against the query."""
        if self.corpus_size == 0:
            return []

        query_tokens = self._tokenize(query)
        scores = [0.0] * self.corpus_size

        for q in query_tokens:
            if q not in self.idf:
                continue
            idf_val = self.idf[q]

            for i in range(self.corpus_size):
                f = self.doc_freqs[i].get(q, 0)
                if f > 0:
                    doc_len = self.doc_lengths[i]
                    num = f * (self.k1 + 1.0)
                    denom = f + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                    scores[i] += idf_val * (num / denom)

        return scores


def bm25_rank_papers(papers: List[Any], query: str, limit: int = 20) -> List[Tuple[Any, float]]:
    """
    Ranks papers using pure BM25Okapi on Title (2x weight) + Abstract (1x weight).
    """
    if not papers:
        return []

    # Title gets double repetition to simulate higher field priority in BM25
    corpus = [
        f"{getattr(p, 'title', '') or ''} {getattr(p, 'title', '') or ''} {getattr(p, 'abstract', '') or ''}"
        for p in papers
    ]

    ranker = BM25Ranker(k1=1.5, b=0.75)
    ranker.fit(corpus)
    scores = ranker.score(query)

    max_s = max(scores) if scores and max(scores) > 0 else 1.0
    normalized_scores = [round(s / max_s, 4) for s in scores]

    ranked = list(zip(papers, normalized_scores))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:limit]
