"""Node 2: Context Handlers (small and large).

Small: inject full text as context, generate summary.
Large: chunk + embed into Chroma, generate summary.
"""

from agents.state import GraphState


def handle_small_context(state: GraphState) -> dict:
    """For assignments under the token threshold — inject full text as context."""
    # TODO (Phase 2): Generate assignment_summary via LLM call.
    return {
        "context_mode": "inject",
        "assignment_summary": f"[placeholder summary of assignment — {state.get('assignment_token_count', 0)} tokens]",
        "assignment_embedded": False,
    }


def handle_large_context(state: GraphState) -> dict:
    """For assignments over the token threshold — chunk, embed, summarize."""
    # TODO (Phase 2): Chunk with RecursiveCharacterTextSplitter,
    # embed into Chroma assignment collection, generate summary via LLM.
    return {
        "context_mode": "rag",
        "assignment_summary": f"[placeholder summary of large assignment — {state.get('assignment_token_count', 0)} tokens]",
        "assignment_embedded": False,  # Will be True once embedding is implemented
    }
