import os
import json
import ast
import typing

try:
    from google import genai
    from google.genai import types
    api_key = os.getenv("GEMINI_API_KEYS")
    if api_key:
        client = genai.Client(api_key=api_key)
    else:
        client = None
except Exception:
    client = None

# Simple in-memory cache to save API calls
_LLM_CACHE = {}

def llm_rerank(query: str, papers: list) -> list:
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
User query: "{query}"

Below are research papers:

{chr(10).join([f"{i+1}. {p.title}" for i,p in enumerate(candidates)])}

Task:
Return the top 5 MOST relevant papers to the query.
Consider domain meaning, not keyword overlap.

Return ONLY indices (as a Python list of integers) like:
[3,1,5,2,4]
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
        content = response.text.strip()
        # Clean up markdown code blocks if the model wrapped it
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
            return reranked
    except Exception as e:
        print(f"LLM Rerank Error: {e}")
    
    return papers


def llm_filter_irrelevant(query: str, papers: list) -> list:
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
Abstract: {str(p.abstract)[:500]}

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

def quick_summary(query: str, papers: list) -> str:
    if not client:
        return "LLM Summary not available without GEMINI_API_KEYS."
        
    if not papers:
        return "Not enough papers to summarize."

    cache_key = f"summary_{query}_{','.join(str(p.id) for p in papers[:5])}"
    if cache_key in _LLM_CACHE:
        return _LLM_CACHE[cache_key]

    prompt = f"""
Summarize the research topic: {query}

Based on papers:
{chr(10).join([p.title for p in papers[:5]])}

Give:
- 2-3 sentence summary
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
        ans = response.text.strip()
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception:
        return "Failed to generate summary."


def literature_review_llm(query: str, papers: list) -> dict:
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

def explain_trend_llm(keyword: str, year: int, papers: list) -> str:
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
        ans = response.text.strip()
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception:
        return "Failed to generate explanation."

def why_this_paper(query: str, paper) -> str:
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
        ans = response.text.strip()
        _LLM_CACHE[cache_key] = ans
        return ans
    except Exception:
        return ""
