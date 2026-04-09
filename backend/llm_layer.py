# pyre-ignore-all-errors
import os
import re
import json
import ast
import typing
from dotenv import load_dotenv

load_dotenv()


def strip_markdown(text: str) -> str:
    """Remove markdown formatting from LLM output for clean frontend display."""
    if not text:
        return text
    text = re.sub(r'```[\s\S]*?```', '', text)  # code blocks
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # bold
    text = re.sub(r'\*(.+?)\*', r'\1', text)  # italic
    text = re.sub(r'^#+\s*', '', text, flags=re.MULTILINE)  # headers
    text = re.sub(r'^[\-\*]\s+', '• ', text, flags=re.MULTILINE)  # bullet points
    text = re.sub(r'\n{3,}', '\n\n', text)  # excess newlines
    
    # Normalize whitespaces and bad punctuation
    text = re.sub(r'[ \t]+', ' ', text)
    text = text.replace(' ,', ',').replace(' .', '.')
    text = text.strip()
    
    # Failsafe for Mistral/OpenRouter stopping mid-sentence
    if text and text[-1] not in ('.', '!', '?'):
        last_period = max(text.rfind('.'), text.rfind('!'), text.rfind('?'))
        if last_period > 0:
            text = text[:last_period+1]
        else:
            text += "..."
            
    return text



_clients = []
_current_client_idx = 0

try:
    from google import genai # pyre-ignore
    from google.genai import types # pyre-ignore
    api_keys_str = os.getenv("GEMINI_API_KEYS", "")
    API_KEYS = [k.strip() for k in api_keys_str.split(",") if k.strip()]
    
    for key in API_KEYS:
        _clients.append(genai.Client(api_key=key))
except Exception:
    pass

def get_gemini_client():
    global _current_client_idx
    if not _clients:
        return None
    client = _clients[_current_client_idx]
    _current_client_idx = (_current_client_idx + 1) % len(_clients)
    return client

# Persistent cache to save API calls
import json

CACHE_FILE = os.path.join(os.path.dirname(__file__), "data", "llm_cache.json")

def load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cache(cache_data):
    try:
        os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump(cache_data, f, indent=2)
    except Exception as e:
        pass

_LLM_CACHE = load_cache()

import requests

def local_summary_fallback(prompt: str, is_json: bool = False):
    d = {
        "summary": "This topic has been analyzed using available research data. Key findings indicate important trends and ongoing developments in this domain.",
        "gaps": ["Limited domain-specific research", "Need for larger datasets"],
        "insights": ["Growing interest in topic", "Emerging interdisciplinary applications"],
        "key_themes": ["Emerging methods", "Cross-domain applications", "Performance optimization"],
        "open_questions": ["How can these methods scale?", "What are the real-world deployment constraints?"]
    }
    
    if is_json:
        if "specific research gaps" in prompt or "JSON array of strings" in prompt:
            return json.dumps(d["gaps"])
        if "Extract structured intent" in prompt:
            return json.dumps({
                "core_terms": [], "context_terms": [], "domain": "", 
                "intent": "", "must_have": [], "avoid": []
            })
        return json.dumps(d)
    return d["summary"]


def call_gemini(prompt: str, max_tokens: int, temperature: float, response_mime_type: typing.Optional[str]):
    client = get_gemini_client()
    if not client:
        raise RuntimeError("No Gemini Client")
    kwargs = {"temperature": temperature, "max_output_tokens": max_tokens}
    if response_mime_type:
        kwargs["response_mime_type"] = response_mime_type
        
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=types.GenerateContentConfig(**kwargs),
    )
    if response.text:
        return response.text
    raise RuntimeError("Empty response")


def call_openrouter(prompt: str, max_tokens: int, temperature: float):
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    if not openrouter_key:
        raise RuntimeError("No OpenRouter Key")
    headers = {
        "Authorization": f"Bearer {openrouter_key}",
        "HTTP-Referer": "http://localhost:8000",
        "X-Title": "ResearchIQ"
    }
    payload = {
        "model": "mistralai/mistral-7b-instruct:free",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": temperature
    }
    res = requests.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload, timeout=15)
    if res.status_code == 200:
        data = res.json()
        if "choices" in data and data["choices"]:
            return data["choices"][0]["message"]["content"]
    raise RuntimeError("Failed OpenRouter completion")


def _call_llm(prompt: str, max_tokens: int = 800, temperature: float = 0.3, response_mime_type: typing.Optional[str] = None) -> str:
    """Multi-LLM fallback chain: Gemini -> OpenRouter -> Local Summary Final Fallback"""
    
    # 1. Try Gemini
    try:
        return call_gemini(prompt, max_tokens, temperature, response_mime_type)
    except Exception as e:
        print(f"Gemini failed: {e}")

    # 2. Try OpenRouter (Free Tier)
    try:
        return call_openrouter(prompt, max_tokens, temperature)
    except Exception as e:
        print(f"OpenRouter failed: {e}")

    # 3. FINAL FALLBACK (never fail)
    print("WARNING: Triggered absolute local_summary_fallback")
    return local_summary_fallback(prompt, is_json=(response_mime_type == "application/json"))

def _extractive_summary(papers: typing.List[typing.Any]) -> str:
    """Absolute last-resort fallback: extracts first 2 sentences from top 3 abstracts."""
    if not papers:
        return "Not enough papers to analyze."
    
    sentences = []
    for p in papers[:3]:
        text = (p.abstract or "").strip()
        if not text:
            text = p.title or ""
            
        import re
        parts = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        if parts:
            sentences.append(f"• {p.title}: {' '.join(parts[:2])}")
            
    if not sentences:
        return "This analysis summarizes key findings across retrieved papers, highlighting major trends, methods, and research directions in this domain."
        
    return "This analysis summarizes key findings across retrieved papers, highlighting major trends, methods, and research directions in this domain.\n\n" + "\n".join(sentences)

def llm_rerank(query: str, papers: typing.List[typing.Any]) -> list:
    client = get_gemini_client()
    if not client:
        return papers

    candidates = papers[:15]
    if not candidates:
        return papers

    cache_key = f"rerank_{query}_{','.join(str(p.id) for p in candidates)}"
    if cache_key in _LLM_CACHE:
        indices = _LLM_CACHE[cache_key]
        try:
            return [candidates[i-1] for i in indices if 1 <= i <= len(candidates)]
        except Exception:
            pass

    prompt = f"""
STRICT INSTRUCTIONS:
Given the user query: "{query}"

Select the top 10 MOST relevant papers from the list below.
- ONLY select papers directly about the query domain.
- REJECT generic domain matches.
- If unsure, EXCLUDE the paper.
- DO NOT guess or hallucinate.

Papers:
{chr(10).join([f"{i+1}. {p.title}" for i,p in enumerate(candidates)])}

Return ONLY indices (as a Python list of integers) like:
[3,1,5,2,4,7,9]
"""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=30,
            ),
        )
        import re
        import json
        
        content = (response.text or "").strip()
        
        # Regex to find the first array-looking string
        match = re.search(r'\[[\d\s,]+\]', content)
        if match:
            try:
                indices = json.loads(match.group(0))
                if isinstance(indices, list):
                    _LLM_CACHE[cache_key] = indices
                    save_cache(_LLM_CACHE)
                    save_cache(_LLM_CACHE)
                    reranked = [candidates[i-1] for i in indices if 1 <= i <= len(candidates)]
                    if len(reranked) < 3:
                        return candidates[:10]  # Fallback
                    return reranked
            except Exception:
                pass
        
        return candidates[:10]
    except Exception as e:
        print(f"LLM Rerank Error: {e}")
        
    return candidates[:10]


def llm_filter_irrelevant(query: str, papers: typing.List[typing.Any]) -> list:
    client = get_gemini_client()
    if not client:
        return papers

    filtered = []
    candidates = papers[:20]

    for p in candidates:
        cache_key = f"filter_{query}_{p.id}"
        if cache_key in _LLM_CACHE:
            if _LLM_CACHE[cache_key]:
                filtered.append(p)
            continue

        prompt = f"""
Query: {query}

Paper title: {p.title}
Abstract: {str(p.abstract)[:500]} # pyre-ignore

Is this paper relevant to the query?

Answer ONLY:
YES or NO
"""
        try:
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=10,
                ),
            )
            ans = response.text.strip().upper()
            is_valid = "YES" in ans
            _LLM_CACHE[cache_key] = is_valid
            save_cache(_LLM_CACHE)
            if is_valid:
                filtered.append(p)
        except Exception as e:
            print(f"LLM Filter Error: {e}")
            filtered.append(p)

    return filtered

def quick_summary(query: str, papers: typing.List[typing.Any]) -> str:
    if not papers:
        return "Not enough papers to summarize."

    cache_key = f"summary_{query}_{','.join(str(p.id) for p in papers[:5])}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    paper_context = chr(10).join([
        f"- {p.title}: {(p.abstract or '')[:200]}" 
        for p in papers[:5]
    ])

    prompt = f"""You are a research analyst. Write a concise, 3-4 sentence executive summary for the topic "{query}" based ONLY on these papers.

Papers:
{paper_context}

Instructions:
- Write a single, cohesive paragraph.
- DO NOT use lists, bullet points, or numbered sections.
- DO NOT use conversational filler like "Here is a summary".
- Explain the current state of research, key techniques, and main trends.
- Be specific and reference actual methods.
- Write complete sentences and do not cut off."""
    try:
        content = _call_llm(prompt, max_tokens=800, temperature=0.3)
        ans = strip_markdown(content.strip())
        
        # Rigorous sentence validation
        import re
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', ans) if len(s.strip()) > 5]
        if len(sentences) < 2:
            raise ValueError("Generated summary is too short or weak, falling back to extractive algorithms.")

        _LLM_CACHE[cache_key] = ans
        save_cache(_LLM_CACHE)
        return ans
    except Exception as e:
        print(f"Summary fallback triggered: {e}")
        # Graceful degradation - never return failure string
        fallback_msg = _extractive_summary(papers)
        # Don't cache the fallback so it tries again later
        return fallback_msg


def literature_review_llm(query: str, papers: typing.List[typing.Any]) -> dict:
    if not papers:
        return {"summary": "No papers available.", "key_themes": [], "open_questions": []}

    cache_key = f"litreview_{query}_{','.join(str(p.id) for p in papers[:10])}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    prompt = f"""
Write a structured literature review for: {query}

Use these papers:
{chr(10).join([p.title for p in papers[:10]])}

Return EXACTLY valid JSON with these keys:
"summary": a short paragraph
"key_themes": list of 3-5 short phrases
"open_questions": list of 2-3 short questions
"""
    try:
        content = _call_llm(prompt, max_tokens=1000, temperature=0.2, response_mime_type="application/json")
        ans = json.loads(content)
        _LLM_CACHE[cache_key] = ans
        save_cache(_LLM_CACHE)
        return ans
    except Exception as e:
        print(f"LLM Lit Review Error: {e}")
        # Graceful fallback instead of failure
        return {
            "summary": _extractive_summary(papers),
            "key_themes": ["Emerging methods", "Cross-domain applications", "Performance optimization"],
            "open_questions": ["How can these methods scale?", "What are the real-world deployment constraints?"]
        }

def explain_trend_llm(keyword: str, year: int, papers: typing.List[typing.Any]) -> str:
    if not papers:
        return "Not enough data to explain."

    cache_key = f"trend_{keyword}_{year}_{','.join(str(p.id) for p in papers[:5])}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    prompt = f"""
Explain why research on "{keyword}" increased in {year}

Papers:
{chr(10).join([p.title for p in papers[:5]])}

Give a 2-3 sentence explanation.
"""
    try:
        content = _call_llm(prompt, max_tokens=150, temperature=0.2)
        ans = strip_markdown(content.strip())
        _LLM_CACHE[cache_key] = ans
        save_cache(_LLM_CACHE)
        return ans
    except Exception:
        return "Explanation unavailable. This trend is likely driven by the key papers published in this period."

def why_this_paper(query: str, paper) -> str:
    cache_key = f"why_{query}_{paper.id}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]
        
    prompt = f"""
Query: {query}
Paper Title: {paper.title}

Briefly explain in 1 sentence why this paper is highly relevant to this exact query domain. 
Do not use generic statements like "This paper discusses...". Be precise.
"""
    try:
        content = _call_llm(prompt, max_tokens=50, temperature=0.1)
        ans = strip_markdown(content.strip())
        _LLM_CACHE[cache_key] = ans
        save_cache(_LLM_CACHE)
        return ans
    except Exception:
        return ""


def parse_query_llm(query: str) -> dict:
    """Extract structured intent (core terms, context terms) from the research query."""
    default_fallback = {
        "core_terms": query.lower().split()[:2],
        "context_terms": [],
        "domain": "",
        "intent": "",
        "must_have": [],
        "avoid": []
    }

    cache_key = f"parse_query_{query.lower().strip()}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    prompt = f"""
    Extract structured intent from this research query.
    Return ONLY valid JSON.
    {{
      "core_terms": [],
      "context_terms": [],
      "domain": "",
      "intent": "",
      "must_have": [],
      "avoid": []
    }}

    Query: {query}
    """

    try:
        content = _call_llm(prompt, max_tokens=150, temperature=0.0, response_mime_type="application/json")
        parsed = json.loads(content)
        
        # Fallback safety rule: MUST have core_terms
        if not parsed.get("core_terms"):
            parsed["core_terms"] = query.lower().split()[:2]
            
        _LLM_CACHE[cache_key] = parsed
        save_cache(_LLM_CACHE)
        return parsed
    except Exception as e:
        print(f"LLM Query Parser Error: {e}")
        return default_fallback


def paper_explain(paper) -> str:
    """Explain a paper simply and identify research gaps."""
    cache_key = f"paper_explain_structured_{getattr(paper, 'id', str(paper))}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    title = getattr(paper, 'title', '') if not isinstance(paper, dict) else paper.get('title', '')
    abstract = getattr(paper, 'abstract', '') if not isinstance(paper, dict) else paper.get('abstract', '')

    prompt = f"""You are an expert research assistant.

Explain the following research paper to a NON-TECHNICAL person.

Paper Title:
{title}

Abstract:
{(abstract or '')[:800]}

Instructions:
1. Explain in simple, clear language (no jargon)
2. Explain what problem the paper is solving
3. Explain how the solution works (high-level)
4. MOST IMPORTANT: Identify the research gap or limitation mentioned or implied

Output format:

Explanation:
<simple explanation>

Research Gap:
- <gap 1>
- <gap 2 (if any)>
"""

    try:
        content = _call_llm(prompt, max_tokens=600, temperature=0.3)
        ans = content.strip()
        _LLM_CACHE[cache_key] = ans
        save_cache(_LLM_CACHE)
        return ans
    except Exception as e:
        print(f"Paper explain error: {e}")
        return f"Explanation:\n{abstract[:300]}...\n\nResearch Gap:\n- Further empirical validation is likely needed."


def generate_gap_sentences(topic: str, papers: list) -> list:
    """Generate 2-3 actionable research gap sentences from papers."""
    paper_ids = ','.join([str(getattr(p, 'id', i)) for i, p in enumerate(papers[:10])])
    cache_key = f"gaps_{topic}_{paper_ids}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    paper_context = chr(10).join([
        f"- {getattr(p, 'title', '') if not isinstance(p, dict) else p.get('title', '')}: {(getattr(p, 'abstract', '') if not isinstance(p, dict) else p.get('abstract', '') or '')[:200]}"
        for p in papers[:10]
    ])

    prompt = f"""You are a research gap analyst. Analyze these papers about "{topic}" and identify 2-3 specific research gaps.

Papers:
{paper_context}

Rules:
- Each gap MUST be concrete and reference specific methods or limitations from the papers
- NO generic phrases like "more research is needed" or "further investigation required"
- Each gap should suggest what is MISSING, UNDEREXPLORED, or CONTRADICTORY
- Be specific to this exact domain

Return ONLY a JSON array of strings like:
["Gap 1 sentence", "Gap 2 sentence", "Gap 3 sentence"]"""

    try:
        content = _call_llm(prompt, max_tokens=400, temperature=0.3, response_mime_type="application/json")
        gaps = json.loads(content.strip())
        if isinstance(gaps, list) and len(gaps) > 0:
            _LLM_CACHE[cache_key] = gaps
            save_cache(_LLM_CACHE)
            return gaps
    except Exception as e:
        print(f"Gap generation error: {e}")
        
    return [
        "Limited cross-domain evaluation of proposed methods across diverse datasets.", 
        "Few studies address real-time deployment constraints in production environments."
    ]


