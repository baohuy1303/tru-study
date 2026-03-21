"""Node 6: Retriever + Response Generator.

Queries ChromaDB with rewritten queries, assembles context window,
and generates a grounded response.
"""

from agents.state import GraphState


def responder(state: GraphState) -> dict:
    """Retrieve relevant chunks and generate final response.

    - Multi-query retrieval from ChromaDB (course_materials + assignment collections)
    - Deduplication and ranking of retrieved chunks
    - Context window assembly (system prompt + assignment + materials + chat history + prompt)
    - LLM call for grounded response generation
    """
    # TODO (Phase 6): Implement full retrieval + response pipeline.
    prompt = state.get("user_prompt", "")
    summary = state.get("assignment_summary", "")

    return {
        "retrieved_docs": [],
        "response": f"[Phase 1 placeholder] Received prompt: \"{prompt}\". Assignment summary: \"{summary}\". Full pipeline not yet implemented.",
    }
