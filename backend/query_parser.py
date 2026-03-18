import re
from nltk.stem import PorterStemmer

stemmer = PorterStemmer()

STOPWORDS = {
    "using","based","method","approach","study","analysis",
    "system","model","paper","propose","framework",
    "for","in","on","of","to","with"
}

LOW_WEIGHT = {"disease", "detection", "classification", "application"}

def normalize(text: str):
    text = text.lower()
    text = text.replace("parkinson's", "parkinson")
    text = text.replace("-", " ")
    return text

def parse_query(query: str):
    query = normalize(query)

    tokens = re.findall(r'\b[a-z0-9]{2,}\b', query)
    tokens = [stemmer.stem(t) for t in tokens if t not in STOPWORDS]

    terms = {}

    # unigram weights
    for t in tokens:
        weight = 1 if t in LOW_WEIGHT else 3
        terms[t] = max(terms.get(t, 0), weight)

    # bigrams (HIGH importance)
    for i in range(len(tokens)-1):
        bg = f"{tokens[i]}_{tokens[i+1]}"
        terms[bg] = 4

    return terms
