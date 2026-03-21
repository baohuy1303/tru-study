"""POST /api/chat — Entry point for the LangGraph multi-agent pipeline."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies import get_bs_token
from agents.graph import build_graph
from utils.session import build_session_id, load_session, append_turn, cache_pipeline_state

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    prompt: str
    course_id: int
    org_unit_id: int
    course_name: str = ""
    assignment_id: int | None = None
    assignment_text: str | None = None  # Instructions text from frontend
    assignment_attachments: list[dict] = []  # [{"file_id", "file_name", "size"}]
    chat_history: list[dict] = []
    selected_topic_ids: list[dict] = []  # [{"id": 123, "title": "Chapter 5.pdf"}]


@router.post("/chat")
async def chat(body: ChatRequest, token: str = Depends(get_bs_token)):
    graph = build_graph()

    # Build session ID and load existing session
    session_id = build_session_id(body.course_id, body.assignment_id)
    session = load_session(session_id)

    # Start with base state from request
    initial_state = {
        "user_prompt": body.prompt,
        "course_id": body.course_id,
        "org_unit_id": body.org_unit_id,
        "course_name": body.course_name,
        "assignment_id": body.assignment_id,
        "assignment_text": body.assignment_text,
        "assignment_attachments": body.assignment_attachments,
        "user_selected_topics": body.selected_topic_ids,
        "bs_token": token,
        "session_id": session_id,
        "pipeline_log": [],
    }

    if session:
        # Use stored chat history (accumulated across turns)
        initial_state["chat_history"] = session.get("chat_history", [])

        # Inject cached pipeline state so nodes can skip work
        cached = session.get("cached_state", {})
        for key, value in cached.items():
            if value is not None:
                initial_state[key] = value
    else:
        initial_state["chat_history"] = body.chat_history

    result = await graph.ainvoke(initial_state)

    # Persist: append this turn and cache pipeline state
    response_text = result.get("response", "")
    append_turn(session_id, body.prompt, response_text)
    cache_pipeline_state(session_id, result)

    return {
        "response": response_text,
        "context_mode": result.get("context_mode"),
        "retrieval_queries": result.get("retrieval_queries", []),
        "session_id": session_id,
        "pipeline_log": result.get("pipeline_log", []),
    }
