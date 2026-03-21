"""Node 2: Context Handlers (small and large).

Small: inject full text as context, generate exhaustive summary via LLM.
Large: chunk + embed into Chroma, generate concise overview via LLM.
"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

from agents.state import GraphState
from utils.chroma import get_assignment_collection
from utils.tokens import count_tokens

load_dotenv()

_llm = None
_embeddings = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=0.3,
        )
    return _llm


def _get_embeddings() -> OpenAIEmbeddings:
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    return _embeddings


def _generate_summary(text: str, course_name: str, detailed: bool) -> str:
    """Generate assignment summary via LLM."""
    if not text.strip():
        return "No assignment text available."

    if detailed:
        system_prompt = (
            f"You are analyzing a university assignment for the course: {course_name}. "
            "Create a thorough, detailed summary that preserves ALL information. Include: "
            "every question/task with its full requirements, all deliverables and submission format, "
            "grading rubric and point breakdowns, deadlines and milestones, required tools/technologies/resources, "
            "formatting requirements, academic integrity notes, and any referenced readings or materials. "
            "Do not omit or simplify anything — the student needs every detail."
        )
    else:
        system_prompt = (
            f"You are analyzing a large university assignment for the course: {course_name}. "
            "Create a detailed but concise overview. Include: the main objective and scope, "
            "all distinct tasks/questions listed with brief descriptions, grading weight per section "
            "if available, key deadlines, required resources or materials referenced, and important "
            "constraints. Be thorough enough that someone reading only this summary understands "
            "the full structure of the assignment, but keep it concise — the full text is stored "
            "separately for retrieval."
        )

    llm = _get_llm()
    response = llm.invoke([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": text},
    ])
    return response.content


def handle_small_context(state: GraphState) -> dict:
    """For assignments under the token threshold — inject full text, generate exhaustive summary."""
    text = state.get("assignment_text", "")
    course_name = state.get("course_name", "Unknown Course")

    summary = _generate_summary(text, course_name, detailed=True)

    return {
        "context_mode": "inject",
        "assignment_summary": summary,
        "assignment_embedded": False,
    }


def handle_large_context(state: GraphState) -> dict:
    """For assignments over the token threshold — chunk, embed into Chroma, generate concise overview."""
    text = state.get("assignment_text", "")
    course_name = state.get("course_name", "Unknown Course")
    assignment_id = state.get("assignment_id")

    # Chunk the assignment text
    splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = splitter.split_text(text)

    # Embed chunks into Chroma
    embedded = False
    if assignment_id and chunks:
        try:
            collection = get_assignment_collection(assignment_id)
            embeddings_model = _get_embeddings()
            vectors = embeddings_model.embed_documents(chunks)

            collection.upsert(
                ids=[f"assignment_{assignment_id}_chunk_{i}" for i in range(len(chunks))],
                documents=chunks,
                embeddings=vectors,
                metadatas=[
                    {"source": "assignment", "chunk_index": i, "assignment_id": str(assignment_id)}
                    for i in range(len(chunks))
                ],
            )
            embedded = True
            print(f"[context_handler] Embedded {len(chunks)} chunks for assignment {assignment_id}")
        except Exception as e:
            print(f"[context_handler] Failed to embed assignment chunks: {e}")

    # Generate concise summary from first ~3000 tokens
    truncated = text
    if count_tokens(text) > 3000:
        # Rough truncation: take first ~12000 chars (~3000 tokens)
        truncated = text[:12000]

    summary = _generate_summary(truncated, course_name, detailed=False)

    return {
        "context_mode": "rag",
        "assignment_summary": summary,
        "assignment_embedded": embedded,
    }
