"""Shared state definition for the LangGraph multi-agent pipeline."""

from typing import TypedDict, Literal
from langchain_core.documents import Document


class GraphState(TypedDict, total=False):
    # ── Input ────────────────────────────────────────────────────────────────
    user_prompt: str
    chat_history: list[dict]          # [{"role": "user"|"assistant", "content": str}]
    assignment_pdf_path: str | None   # Local path to uploaded PDF
    assignment_text: str | None       # Raw text from instructions or PDF
    course_id: int
    org_unit_id: int
    course_name: str                  # Course name for summary context
    assignment_id: int | None         # Brightspace dropbox folder ID
    assignment_attachments: list[dict] # [{"file_id": int, "file_name": str, "size": int}]
    bs_token: str                     # Brightspace Bearer token for API calls

    # ── PDF processing ───────────────────────────────────────────────────────
    assignment_token_count: int
    context_mode: Literal["inject", "rag"]
    assignment_summary: str
    assignment_embedded: bool

    # ── Material extraction ──────────────────────────────────────────────────
    material_references: list[dict]   # [{"name", "material_type", "context_hint"}]

    # ── Material fetching ────────────────────────────────────────────────────
    embedded_materials: list[str]     # Filenames of embedded materials
    materials_metadata: dict          # Manifest data

    # ── Retrieval ────────────────────────────────────────────────────────────
    retrieval_queries: list[str]
    retrieved_docs: list[Document]

    # ── Output ───────────────────────────────────────────────────────────────
    response: str
