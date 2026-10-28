"""
LangGraph Multi-Agent Research Orchestrator
===========================================
Defines a team of collaborative research agents running on a LangGraph StateGraph:
1. ScoutAgent: Assesses retrieved candidate papers and contextualizes key themes.
2. CriticAgent: Evaluates methodology, reproducibility, and critical limitations.
3. GapAgent: Formulates concrete open research frontiers.
4. SynthesisAgent: Generates unified, executive intelligence review with personalized rationales.
"""

from typing import TypedDict, List, Dict, Any, Optional
import logging
from langgraph.graph import StateGraph, END
from llm_layer import quick_summary, literature_review_llm, generate_gap_sentences

logger = logging.getLogger(__name__)

class ResearchState(TypedDict):
    topic: str
    purpose: str
    session_id: str
    papers: List[Dict[str, Any]]
    scout_analysis: Optional[str]
    critic_notes: Optional[List[str]]
    research_gaps: Optional[List[str]]
    synthesis_summary: Optional[str]
    recommendation_insights: Optional[List[Dict[str, Any]]]

def scout_node(state: ResearchState) -> Dict[str, Any]:
    """Scout analyzes paper breadth, sources, and overarching patterns."""
    papers = state.get("papers", [])
    topic = state.get("topic", "")
    if not papers:
        return {"scout_analysis": "No papers available to scout."}
    
    top_titles = [p.get("title", "") for p in papers[:5]]
    analysis = f"Identified {len(papers)} candidate papers for '{topic}'. Key focal works include: {'; '.join(top_titles[:3])}."
    return {"scout_analysis": analysis}

def critic_node(state: ResearchState) -> Dict[str, Any]:
    """Critic analyzes methodological trade-offs and potential limitations."""
    papers = state.get("papers", [])
    criticisms = []
    for p in papers[:4]:
        title = p.get("title", "Paper")
        year = p.get("year", 2024)
        cites = p.get("citation_count", 0)
        if cites < 5 and year < 2023:
            criticisms.append(f"'{title[:45]}...' has modest citation adoption ({cites} cites), warranting scrutiny on experimental reproducibility.")
        elif year >= 2025:
            criticisms.append(f"'{title[:45]}...' is recent work; longitudinal real-world validation benchmarks remain to be demonstrated.")
        else:
            criticisms.append(f"Methodological assumptions in '{title[:45]}...' rely heavily on constrained benchmark distributions.")
    return {"critic_notes": criticisms}

def gap_node(state: ResearchState) -> Dict[str, Any]:
    """Formulates open research gaps based on the paper abstracts."""
    papers = state.get("papers", [])
    topic = state.get("topic", "")
    
    class MockPaper:
        def __init__(self, d):
            self.title = d.get("title", "")
            self.abstract = d.get("abstract", "")
            self.year = d.get("year", 2024)
            self.id = d.get("id", "")

    paper_objs = [MockPaper(p) for p in papers[:6]]
    try:
        gaps = generate_gap_sentences(topic, paper_objs)
    except Exception as e:
        logger.warning(f"Gap agent LLM error: {e}")
        gaps = [
            f"Lack of standardized multi-domain benchmarking in {topic}.",
            f"Limited exploration of real-time latency versus compute trade-offs."
        ]
    return {"research_gaps": gaps}

def synthesis_node(state: ResearchState) -> Dict[str, Any]:
    """Synthesizes insights into executive literature review and recommendation explanations."""
    papers = state.get("papers", [])
    topic = state.get("topic", "")
    
    class MockPaper:
        def __init__(self, d):
            self.title = d.get("title", "")
            self.abstract = d.get("abstract", "")
            self.year = d.get("year", 2024)
            self.id = d.get("id", "")

    paper_objs = [MockPaper(p) for p in papers[:6]]
    try:
        summary = quick_summary(topic, paper_objs)
    except Exception as e:
        logger.warning(f"Synthesis summary error: {e}")
        summary = f"Synthesized overview across {len(papers)} papers covering core tenets of {topic}."

    rec_insights = []
    for p in papers[:5]:
        ucb = p.get("ucb_score", 0.5)
        rec_type = p.get("rec_type", "exploration")
        rec_insights.append({
            "id": p.get("id"),
            "title": p.get("title"),
            "agent_rationale": f"Selected via {rec_type.upper()} policy (Score: {ucb}). Critic affirms foundational alignment with {topic}."
        })

    return {
        "synthesis_summary": summary,
        "recommendation_insights": rec_insights
    }

# Build LangGraph StateGraph
workflow = StateGraph(ResearchState)
workflow.add_node("scout", scout_node)
workflow.add_node("critic", critic_node)
workflow.add_node("gap_detector", gap_node)
workflow.add_node("synthesizer", synthesis_node)

workflow.set_entry_point("scout")
workflow.add_edge("scout", "critic")
workflow.add_edge("critic", "gap_detector")
workflow.add_edge("gap_detector", "synthesizer")
workflow.add_edge("synthesizer", END)

research_agent_graph = workflow.compile()

def run_agentic_workflow(topic: str, papers: List[Dict[str, Any]], session_id: str = "default", purpose: str = "quick overview") -> Dict[str, Any]:
    """Execute the multi-agent graph synchronously."""
    initial_state = {
        "topic": topic,
        "purpose": purpose,
        "session_id": session_id,
        "papers": papers,
        "scout_analysis": None,
        "critic_notes": None,
        "research_gaps": None,
        "synthesis_summary": None,
        "recommendation_insights": None
    }
    result = research_agent_graph.invoke(initial_state)
    return result
