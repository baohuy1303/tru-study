"""Node 5: Query Rewriter.

Transforms user prompt + chat history + assignment summary into
2-3 semantically diverse retrieval queries for ChromaDB.
"""

import os
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI

from agents.state import GraphState

load_dotenv()


class RewrittenQueries(BaseModel):
    queries: list[str]


_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=0.3,
        )
    return _llm


SYSTEM_PROMPT = """You are a search query optimizer for a university course assistant.

Given a student's question, the assignment summary, and recent chat history, generate exactly 2-3 search queries optimized for embedding similarity search against chunked course materials (textbook chapters, lecture slides, lab documents).

Rules:
1. Each query should be semantically DIVERSE — target different angles:
   - One conceptual (what is the topic, definitions, theory)
   - One procedural (how to do it, steps, implementation)
   - One assignment-specific (ties directly to the assignment requirements)
2. Expand abbreviations and vague references. "Q3" is useless — use the assignment summary to determine what Question 3 is about and write a descriptive query.
3. If chat history shows the student is following up ("what about the next part?", "can you explain more?"), resolve the reference using prior messages.
4. Use domain-specific terminology from the course. Avoid vague queries like "help with assignment".
5. Each query should be 10-25 words, descriptive enough to match against chunked course material text."""


def query_rewriter(state: GraphState) -> dict:
    """Rewrite user prompt into 2-3 retrieval-optimized queries."""
    import time
    from utils.pipeline_log import log_step
    
    t0 = time.time()
    
    prompt = state.get("user_prompt", "")
    if not prompt.strip():
        return {"retrieval_queries": [], "pipeline_log": log_step(state, "query_rewriter", "skipped", "empty prompt", time.time() - t0)}

    summary = state.get("assignment_summary", "")
    chat_history = state.get("chat_history", [])
    recent_history = chat_history[-5:] if chat_history else []

    # Build user message with all available context
    parts = [f"Student's question: {prompt}"]
    if summary:
        parts.append(f"\nAssignment summary:\n{summary}")
    if recent_history:
        history_text = "\n".join(
            f"  {msg.get('role', 'user')}: {msg.get('content', '')}"
            for msg in recent_history
        )
        parts.append(f"\nRecent chat history:\n{history_text}")

    user_message = "\n".join(parts)

    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(RewrittenQueries)
        result = structured_llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ])

        queries = [q.strip() for q in result.queries if q.strip()]
        if queries:
            print(f"[query_rewriter] Generated {len(queries)} queries:")
            for q in queries:
                print(f"  - {q}")
                
            elapsed = time.time() - t0
            return {"retrieval_queries": queries, "pipeline_log": log_step(state, "query_rewriter", "done", f"generated {len(queries)} diverse queries", elapsed)}

    except Exception as e:
        print(f"[query_rewriter] LLM rewriting failed: {e}")

    # Fallback: use original prompt
    print(f"[query_rewriter] Falling back to original prompt")
    return {"retrieval_queries": [prompt], "pipeline_log": log_step(state, "query_rewriter", "warning", "generation failed, falling back to original prompt", time.time() - t0)}
