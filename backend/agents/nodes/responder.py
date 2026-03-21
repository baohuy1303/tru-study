"""Node 6: Retriever + Response Generator.

Queries ChromaDB with rewritten queries, assembles context window,
and generates a grounded response.
"""

import os
from collections import Counter

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from agents.state import GraphState
from utils.chroma import get_course_materials_collection, get_assignment_collection
from utils.tokens import count_tokens

load_dotenv()

MAX_CONTEXT_TOKENS = int(os.getenv("MAX_CONTEXT_TOKENS", "16000"))
MATERIAL_TOP_K = 3   # per query, from course_materials collection
ASSIGNMENT_TOP_K = 2  # per query, from assignment collection
MAX_CHUNKS = 10       # after dedup + ranking

_llm = None
_embeddings = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=0.4,
        )
    return _llm


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    return _embeddings


SYSTEM_PROMPT = """You are TruStudy, an AI study assistant for university students. You help students understand their assignments and course materials.

Guidelines:
1. Ground your answers in the provided course materials and assignment context. When referencing specific materials, cite them naturally (e.g. "According to Chapter 5...", "As shown in the lecture slides...").
2. Guide students toward understanding rather than giving direct answers to graded questions. Help them think through the problem step by step.
3. If the student asks about something not covered in the provided materials, say so honestly rather than guessing. You can still offer general guidance but note it's not from course materials.
4. Be clear, concise, and educational. Use examples when they help illustrate concepts.
5. If the question is vague, ask for clarification rather than assuming.
6. If no course materials were provided or retrieved, acknowledge this. You can still help using the assignment context and your general knowledge, but note that your response isn't grounded in specific course materials. Suggest the student manually select relevant files if available."""


def _retrieve_chunks(
    queries: list[str],
    course_id: int | None,
    assignment_id: int | None,
    context_mode: str,
) -> list[dict]:
    """Run multi-query retrieval against ChromaDB collections.

    Returns list of {"id": str, "text": str, "source": str, "distance": float}.
    """
    if not queries:
        return []

    embeddings_model = _get_embeddings()
    all_results = []  # (chunk_id, text, source, distance)

    for query in queries:
        try:
            query_vector = embeddings_model.embed_query(query)
        except Exception as e:
            print(f"[responder] Failed to embed query '{query[:50]}...': {e}")
            continue

        # Search course materials collection
        if course_id:
            try:
                collection = get_course_materials_collection(course_id)
                if collection.count() > 0:
                    results = collection.query(
                        query_embeddings=[query_vector],
                        n_results=min(MATERIAL_TOP_K, collection.count()),
                    )
                    for i, doc_id in enumerate(results["ids"][0]):
                        all_results.append({
                            "id": doc_id,
                            "text": results["documents"][0][i],
                            "source": results["metadatas"][0][i].get("source", "course material"),
                            "distance": results["distances"][0][i] if results.get("distances") else 0,
                        })
            except Exception as e:
                print(f"[responder] Course materials query failed: {e}")

        # Search assignment collection (only in RAG mode)
        if context_mode == "rag" and assignment_id:
            try:
                collection = get_assignment_collection(assignment_id)
                if collection.count() > 0:
                    results = collection.query(
                        query_embeddings=[query_vector],
                        n_results=min(ASSIGNMENT_TOP_K, collection.count()),
                    )
                    for i, doc_id in enumerate(results["ids"][0]):
                        all_results.append({
                            "id": doc_id,
                            "text": results["documents"][0][i],
                            "source": "assignment",
                            "distance": results["distances"][0][i] if results.get("distances") else 0,
                        })
            except Exception as e:
                print(f"[responder] Assignment collection query failed: {e}")

    return all_results


def _dedup_and_rank(results: list[dict]) -> list[dict]:
    """Deduplicate by chunk ID, boost chunks that appear for multiple queries."""
    # Count occurrences of each chunk ID
    id_counts = Counter(r["id"] for r in results)

    # Keep first occurrence of each, with occurrence count as boost
    seen = set()
    unique = []
    for r in results:
        if r["id"] not in seen:
            seen.add(r["id"])
            unique.append({**r, "boost": id_counts[r["id"]]})

    # Sort: more occurrences first, then lower distance
    unique.sort(key=lambda x: (-x["boost"], x["distance"]))

    return unique[:MAX_CHUNKS]


def _build_messages(
    system_prompt: str,
    assignment_context: str,
    chunks: list[dict],
    chat_history: list[dict],
    user_prompt: str,
) -> list[dict]:
    """Assemble the LLM messages with token budget management."""
    messages = [{"role": "system", "content": system_prompt}]
    budget_used = count_tokens(system_prompt) + count_tokens(user_prompt) + 200  # buffer

    # 1. Assignment context (high priority)
    if assignment_context:
        assignment_tokens = count_tokens(assignment_context)
        if budget_used + assignment_tokens < MAX_CONTEXT_TOKENS:
            messages.append({
                "role": "system",
                "content": f"Assignment context:\n{assignment_context}",
            })
            budget_used += assignment_tokens

    # 2. Retrieved chunks (medium priority)
    if chunks:
        chunk_parts = []
        for chunk in chunks:
            chunk_text = f"[Source: {chunk['source']}]\n{chunk['text']}"
            chunk_tokens = count_tokens(chunk_text)
            if budget_used + chunk_tokens >= MAX_CONTEXT_TOKENS:
                break
            chunk_parts.append(chunk_text)
            budget_used += chunk_tokens

        if chunk_parts:
            materials_text = "\n\n---\n\n".join(chunk_parts)
            messages.append({
                "role": "system",
                "content": f"Retrieved course materials:\n\n{materials_text}",
            })

    # 3. Chat history (low priority — truncate oldest first)
    if chat_history:
        history_to_include = []
        for msg in reversed(chat_history[-10:]):
            msg_tokens = count_tokens(msg.get("content", ""))
            if budget_used + msg_tokens >= MAX_CONTEXT_TOKENS:
                break
            history_to_include.insert(0, msg)
            budget_used += msg_tokens

        for msg in history_to_include:
            messages.append({
                "role": msg.get("role", "user"),
                "content": msg.get("content", ""),
            })

    # 4. User prompt (always included)
    messages.append({"role": "user", "content": user_prompt})

    return messages


def responder(state: GraphState) -> dict:
    """Retrieve relevant chunks and generate final response."""
    import time
    from utils.pipeline_log import log_step
    
    t0 = time.time()
    
    queries = state.get("retrieval_queries", [])
    course_id = state.get("course_id")
    assignment_id = state.get("assignment_id")
    context_mode = state.get("context_mode", "inject")
    user_prompt = state.get("user_prompt", "")
    chat_history = state.get("chat_history", [])
    assignment_text = state.get("assignment_text", "")
    assignment_summary = state.get("assignment_summary", "")

    # Step 1: Multi-query retrieval
    raw_results = _retrieve_chunks(queries, course_id, assignment_id, context_mode)
    print(f"[responder] Retrieved {len(raw_results)} raw chunks from {len(queries)} queries")

    # Step 2: Dedup and rank
    ranked_chunks = _dedup_and_rank(raw_results)
    print(f"[responder] {len(ranked_chunks)} unique chunks after dedup/ranking")

    # Empty Retrieval notification
    if not ranked_chunks:
        user_prompt = (
            "[System note: No course materials were retrieved for this query. "
            "If you have relevant course files (slides, textbook chapters, lab guides), "
            "you can select them using the checkboxes in the course sidebar on the left. "
            "Responding based on assignment context and general knowledge for now.]\n\n"
            + user_prompt
        )

    # Step 3: Build assignment context based on mode
    if context_mode == "inject":
        # Small assignment — use full text
        assignment_context = assignment_text or assignment_summary
    else:
        # Large assignment (RAG) — use summary only, chunks handle the detail
        assignment_context = assignment_summary

    # Safeguard: if assignment_context alone exceeds the budget roughly, fall back to summary/truncation
    if assignment_context and count_tokens(assignment_context) > MAX_CONTEXT_TOKENS - 2000:
        print("[responder] Warning: assignment_context too large for budget. Falling back to summary/truncation.")
        assignment_context = assignment_summary or assignment_context[:12000]

    # Step 4: Assemble messages with token budget
    messages = _build_messages(
        system_prompt=SYSTEM_PROMPT,
        assignment_context=assignment_context,
        chunks=ranked_chunks,
        chat_history=chat_history,
        user_prompt=user_prompt,
    )

    # Step 5: Generate response
    try:
        llm = _get_llm()
        response = llm.invoke(messages)
        response_text = response.content
        print(f"[responder] Generated response ({len(response_text)} chars)")
    except Exception as e:
        print(f"[responder] LLM response generation failed: {e}")
        response_text = "I'm sorry, I encountered an error generating a response. Please try again."

    # Convert ranked chunks to LangChain Documents for state
    retrieved_docs = [
        Document(
            page_content=chunk["text"],
            metadata={"source": chunk["source"], "distance": chunk["distance"]},
        )
        for chunk in ranked_chunks
    ]

    elapsed = time.time() - t0
    print(f"[responder] Done in {elapsed:.1f}s")

    return {
        "retrieved_docs": retrieved_docs,
        "response": response_text,
        "pipeline_log": log_step(state, "responder", "done", f"retrieved {len(ranked_chunks)} chunks", elapsed)
    }
