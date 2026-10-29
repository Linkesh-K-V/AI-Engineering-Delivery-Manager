from typing import TypedDict, List, Optional, Any
from langgraph.graph import StateGraph, END
from models import TaskExtraction, CandidateProfile, AssignmentRecommendation
from llm_parser import parse_manager_request
from candidate_engine import rank_candidates
from llm_reasoner import generate_recommendation

# 1. Define the Graph State Schema
class DeliveryManagerState(TypedDict):
    manager_prompt: str
    parsed_task: Optional[TaskExtraction]
    top_candidates: List[CandidateProfile]
    ai_recommendation: Optional[AssignmentRecommendation]
    error: Optional[str]
    session: Optional[Any]
    rejected_candidates: Optional[List[str]]

# 2. Define Individual Graph Nodes
def jev_parser_node(state: DeliveryManagerState) -> dict:
    """System 1 (Jev): Converts unstructured prompt to Pydantic TaskExtraction with strict typing."""
    try:
        task = parse_manager_request(state["manager_prompt"])
        return {"parsed_task": task}
    except Exception as e:
        return {"error": f"Task parsing failed: {str(e)}"}

def candidate_math_node(state: DeliveryManagerState) -> dict:
    """Deterministic Math Engine: Evaluates skills, calendar capacity & variance calibration."""
    if state.get("error"):
        return {}
    try:
        task = state["parsed_task"]
        session = state.get("session")
        rejected_candidates = state.get("rejected_candidates")
        candidates = rank_candidates(task, session=session, rejected_candidates=rejected_candidates)
        # Pass the top 3 candidates to the reasoner
        return {"top_candidates": candidates[:3]}
    except Exception as e:
        return {"error": f"Candidate ranking failed: {str(e)}"}

def llama_reasoner_node(state: DeliveryManagerState) -> dict:
    """System 2 (Llama 3): Synthesizes facts into human-readable trade-off reasoning."""
    if state.get("error"):
        return {}
    try:
        recommendation = generate_recommendation(
            task=state["parsed_task"],
            top_candidates=state["top_candidates"]
        )
        return {"ai_recommendation": recommendation}
    except Exception as e:
        return {"error": f"Reasoning generation failed: {str(e)}"}

# Aliases for backward compatibility
parse_task_node = jev_parser_node
rank_candidates_node = candidate_math_node
reason_recommendation_node = llama_reasoner_node

# 3. Assemble and Compile the Graph
workflow = StateGraph(DeliveryManagerState)

workflow.add_node("jev_parser_node", jev_parser_node)
workflow.add_node("candidate_math_node", candidate_math_node)
workflow.add_node("llama_reasoner_node", llama_reasoner_node)

# Explicit routing: jev_parser_node -> candidate_math_node -> llama_reasoner_node -> END
workflow.set_entry_point("jev_parser_node")
workflow.add_edge("jev_parser_node", "candidate_math_node")
workflow.add_edge("candidate_math_node", "llama_reasoner_node")
workflow.add_edge("llama_reasoner_node", END)

orchestrator_app = workflow.compile()
