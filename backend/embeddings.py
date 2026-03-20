import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2")

def build_index(papers):
    if not papers:
        return None, None
        
    texts = [(p.title or "") + " " + (p.abstract or "") for p in papers]
    embeddings = model.encode(texts)
    
    # 384 is the embedding dimension for all-MiniLM-L6-v2
    index = faiss.IndexFlatL2(384)
    index.add(np.array(embeddings).astype("float32"))
    
    return index, embeddings

def semantic_search(query: str, papers: list, index):
    if not papers or not index:
        return []
        
    q_emb = model.encode([query])
    
    # If k is larger than the number of papers, Faiss behaves gracefully up to num papers, 
    # but safe to bound it
    k = min(20, len(papers))
    
    D, I = index.search(np.array(q_emb).astype("float32"), k=k)
    
    # I contains the indices in the candidates list
    return [papers[i] for i in I[0] if i >= 0 and i < len(papers)]
