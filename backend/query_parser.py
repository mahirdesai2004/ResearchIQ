import re
from nltk.stem import PorterStemmer

stemmer = PorterStemmer()

STOPWORDS = {
    "using", "based", "method", "approach", "study", "analysis",
    "system", "model", "paper", "propose", "framework",
    "for", "in", "on", "of", "to", "with", "the", "and", "how",
    "do", "does", "can", "what", "which", "where", "when", "why",
    "are", "is", "was", "were", "been", "being", "have", "has",
    "this", "that", "these", "those", "about", "from"
}

LOW_WEIGHT = {
    "disease", "diseas", 
    "detection", "detect", 
    "classification", "classif", 
    "application", "applic"
}

# Acronym expansion map
ACRONYM_MAP = {
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "dl": "deep learning",
    "rl": "reinforcement learning",
    "eeg": "electroencephalography",
    "cnn": "convolutional neural network",
    "rnn": "recurrent neural network",
    "gan": "generative adversarial network",
    "llm": "large language model",
    "iot": "internet of things",
    "nn": "neural network",
}

def normalize(text: str):
    text = text.lower()
    text = text.replace("parkinson's", "parkinson")
    text = text.replace("-", " ")
    return text

def parse_query(query: str):
    query = normalize(query)

    # Expand acronyms FIRST (before tokenization)
    expanded_parts = []
    raw_tokens = query.split()
    for t in raw_tokens:
        t_clean = t.strip()
        if t_clean in ACRONYM_MAP:
            expanded_parts.append(ACRONYM_MAP[t_clean])
        else:
            expanded_parts.append(t_clean)
    query = " ".join(expanded_parts)

    # Allow 2+ character tokens (captures "ml", "ai", etc.)
    tokens = re.findall(r'\b[a-z0-9]{2,}\b', query)
    tokens = [stemmer.stem(t) for t in tokens if t not in STOPWORDS]

    terms = {}

    for t in tokens:
        if t in LOW_WEIGHT:
            terms[t] = 1
        else:
            terms[t] = 5  # high importance for specific terms

    # bigrams VERY STRONG
    for i in range(len(tokens) - 1):
        bg = f"{tokens[i]}_{tokens[i+1]}"
        terms[bg] = 10

    return terms
