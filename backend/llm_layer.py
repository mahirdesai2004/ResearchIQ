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
    return text.strip()



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

# Simple in-memory cache to save API calls
_LLM_CACHE = {}

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
        content = (response.text or "").strip()
        if content.startswith("```"):
            lines = content.split("\n")
            if len(lines) > 1:
                content = lines[1]
            if content.endswith("```"):
                content = content[:-3]
        indices = ast.literal_eval(content.strip())
        if isinstance(indices, list):
            _LLM_CACHE[cache_key] = indices
            reranked = [candidates[i-1] for i in indices if 1 <= i <= len(candidates)]
            if len(reranked) < 3:
                return candidates[:10]  # Fallback
            return reranked
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
            if is_valid:
                filtered.append(p)
        except Exception as e:
            print(f"LLM Filter Error: {e}")
            filtered.append(p)

    return filtered

def quick_summary(query: str, papers: typing.List[typing.Any]) -> str:
    client = get_gemini_client()
    if not client:
        return "LLM Summary not available without GEMINI_API_KEYS."
        
    if not papers:
        return "Not enough papers to summarize."

    cache_key = f"summary_{query}_{','.join(str(p.id) for p in papers[:5])}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    paper_context = chr(10).join([
        f"- {p.title}: {(p.abstract or '')[:200]}" 
        for p in papers[:5]
    ])

    prompt = f"""You are a research analyst. Write a complete analysis.

Given these papers on "{query}", generate:

1. A 3-4 sentence executive summary explaining the current state of research
2. Key techniques and methods being used (list 3-5)
3. The main trend or direction in this field

Papers:
{paper_context}

Be specific. Reference actual methods and findings. No generic statements. Write complete sentences - do not cut off mid-sentence."""
    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=800,
            ),
        )
        ans = strip_markdown(response.text.strip())
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception:
        return "Failed to generate summary."


def literature_review_llm(query: str, papers: typing.List[typing.Any]) -> dict:
    client = get_gemini_client()
    if not client:
        return {
            "summary": "LLM Features not configured.",
            "key_themes": [],
            "open_questions": []
        }

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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            ),
        )
        content = response.text.strip()
        ans = json.loads(content)
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception as e:
        print(f"LLM Lit Review Error: {e}")
        return {
            "summary": "Failed to generate literature review.",
            "key_themes": [],
            "open_questions": []
        }

def explain_trend_llm(keyword: str, year: int, papers: typing.List[typing.Any]) -> str:
    client = get_gemini_client()
    if not client:
        return "LLM Features not configured."
        
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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=150,
            ),
        )
        ans = strip_markdown(response.text.strip())
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception:
        return "Failed to generate explanation."

def why_this_paper(query: str, paper) -> str:
    client = get_gemini_client()
    if not client:
        return ""

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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=50,
            ),
        )
        ans = strip_markdown(response.text.strip())
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception:
        return ""


def parse_query_llm(query: str) -> dict:
    """Extract structured intent (core terms, context terms) from the research query."""
    client = get_gemini_client()
    default_fallback = {
        "core_terms": query.lower().split()[:2],
        "context_terms": [],
        "domain": "",
        "intent": "",
        "must_have": [],
        "avoid": []
    }
    
    if not client:
        return default_fallback

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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        content = (response.text or "").strip()
        parsed = json.loads(content)
        
        # Fallback safety rule: MUST have core_terms
        if not parsed.get("core_terms"):
            parsed["core_terms"] = query.lower().split()[:2]
            
        _LLM_CACHE[cache_key] = parsed
        return parsed
    except Exception as e:
        print(f"LLM Query Parser Error: {e}")
        return default_fallback


def paper_explain(paper) -> str:
    """Explain a paper simply and identify research gaps."""
    client = get_gemini_client()
    if not client:
        return "Explanation:\nLLM not configured.\n\nResearch Gap:\n- N/A"

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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(temperature=0.3, max_output_tokens=600),
        )
        ans = response.text.strip()
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception as e:
        print(f"Paper explain error: {e}")
        return "Explanation:\nFailed to generate explanation.\n\nResearch Gap:\n- Could not identify gaps."


def generate_gap_sentences(topic: str, papers: list) -> list:
    """Generate 2-3 actionable research gap sentences from papers."""
    client = get_gemini_client()
    if not client:
        return ["LLM not configured for gap detection."]

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
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
                max_output_tokens=400,
            ),
        )
        gaps = json.loads(response.text.strip())
        if isinstance(gaps, list) and len(gaps) > 0:
            _LLM_CACHE[cache_key] = gaps
            return gaps
    except Exception as e:
        print(f"Gap generation error: {e}")
    return ["Limited cross-domain evaluation of proposed methods across diverse datasets.", 
            "Few studies address real-time deployment constraints in production environments."]


