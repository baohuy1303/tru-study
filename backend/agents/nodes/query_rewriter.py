"""Node 5: Query Rewriter.

Transforms user prompt + chat history + assignment summary into
2-3 semantically diverse retrieval queries for ChromaDB.
"""

from agents.state import GraphState


def query_rewriter(state: GraphState) -> dict:
    """Rewrite user prompt into retrieval-optimized queries.

    Uses LLM to generate 2-3 focused queries that are:
    - Semantically diverse (conceptual, procedural, assignment-specific)
    - Chat-history-aware (resolves references like "the next part")
    - Domain-specific (uses course terminology)
    """
    # TODO (Phase 5): Use LLM with structured output (queries: list[str])
    # fed with user_prompt, chat_history[-5:], and assignment_summary.
    prompt = state.get("user_prompt", "")
    return {
        "retrieval_queries": [prompt] if prompt else [],
    }
