# pyre-ignore-all-errors
"""
LangChain-powered Chat Engine for ResearchIQ.
Provides a research assistant that answers questions grounded in paper abstracts.
"""
import os
import typing
from dotenv import load_dotenv

load_dotenv()

# In-memory conversation store keyed by session
_conversations: dict = {}

def _get_llm():
    """Get a LangChain ChatGoogleGenerativeAI instance with key rotation."""
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        api_keys_str = os.getenv("GEMINI_API_KEYS", "")
        keys = [k.strip() for k in api_keys_str.split(",") if k.strip()]
        if not keys:
            return None
        # Simple rotation via global counter
        global _key_idx
        if not hasattr(typing, '_chat_key_idx'):
            typing._chat_key_idx = 0
        key = keys[typing._chat_key_idx % len(keys)]
        typing._chat_key_idx += 1
        return ChatGoogleGenerativeAI(
            model="gemini-2.5-flash",
            google_api_key=key,
            temperature=0.3,
            max_output_tokens=500,
        )
    except Exception as e:
        print(f"Chat LLM init error: {e}")
        return None


def build_context(papers: list, max_papers: int = 7) -> str:
    """Build a context string from paper abstracts, safely truncated."""
    context_parts = []
    for i, p in enumerate(papers[:max_papers]):
        title = p.get("title", "Untitled") if isinstance(p, dict) else getattr(p, "title", "Untitled")
        abstract = p.get("abstract", "") if isinstance(p, dict) else getattr(p, "abstract", "")
        pid = p.get("id", f"paper_{i}") if isinstance(p, dict) else getattr(p, "id", f"paper_{i}")
        # Truncate abstract to 400 chars
        short = (abstract or "")[:400]
        context_parts.append(f"[{pid}] {title}\n{short}")
    return "\n\n".join(context_parts)


def chat_with_papers(query: str, papers: list, session_id: str = "default") -> dict:
    """
    Chat with research papers using LangChain.
    Returns { answer: str, sources: list[str] }
    """
    llm = _get_llm()
    if not llm:
        return {
            "answer": "Chat is not available. Please configure GEMINI_API_KEYS.",
            "sources": []
        }

    context = build_context(papers)
    
    # Get or create conversation history
    if session_id not in _conversations:
        _conversations[session_id] = []
    history = _conversations[session_id]

    # Build history string (last 6 messages)
    history_str = ""
    for msg in history[-6:]:
        role = msg["role"]
        content = msg["content"]
        history_str += f"{role}: {content}\n"

    prompt = f"""You are a research assistant. Answer the user's question using ONLY the provided research papers as context.

Rules:
- Be concise and specific
- Cite paper IDs in brackets like [paper_id] when referencing
- If the papers don't contain enough information, say "Based on the available papers, I don't have enough information to answer this."
- Do NOT make up information not present in the papers

Context Papers:
{context}

{f"Conversation History:{chr(10)}{history_str}" if history_str else ""}

User Question: {query}

Answer:"""

    try:
        response = llm.invoke(prompt)
        answer = response.content.strip()
        
        # Extract cited paper IDs
        import re
        cited = re.findall(r'\[([^\]]+)\]', answer)
        sources = [s for s in cited if not s.startswith("paper_")]
        
        # Save to history
        history.append({"role": "User", "content": query})
        history.append({"role": "Assistant", "content": answer})
        # Keep history manageable
        if len(history) > 20:
            _conversations[session_id] = history[-20:]
        
        return {"answer": answer, "sources": sources}
    except Exception as e:
        print(f"Chat error: {e}")
        return {
            "answer": f"I encountered an error processing your question. Please try again.",
            "sources": []
        }


def clear_session(session_id: str = "default"):
    """Clear conversation history for a session."""
    if session_id in _conversations:
        del _conversations[session_id]
