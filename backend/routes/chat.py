"""POST /api/chat — Entry point for the LangGraph multi-agent pipeline."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies import get_bs_token
from agents.graph import build_graph
from utils.session import build_session_id, load_session, append_turn, cache_pipeline_state, delete_session, delete_all_sessions, get_task_plan, update_task_plan

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    prompt: str
    mode: str = "neutral"
    course_id: int
    org_unit_id: int
    course_name: str = ""
    assignment_id: int | None = None
    assignment_text: str | None = None  # Instructions text from frontend
    assignment_attachments: list[dict] = []  # [{"file_id", "file_name", "size"}]
    chat_history: list[dict] = []
    selected_topic_ids: list[dict] = []  # [{"id": 123, "title": "Chapter 5.pdf"}]
    uploaded_files: list[dict] = []      # [{"file_id", "file_name", "path", "is_main": bool}]
    session_id: str | None = None


from fastapi.responses import StreamingResponse
import json

@router.post("/chat/stream")
async def chat_stream(body: ChatRequest, token: str = Depends(get_bs_token)):
    graph = build_graph()

    # Build session ID and load existing session
    session_id = body.session_id
    if not session_id:
        if body.assignment_id:
            session_id = build_session_id(body.course_id, body.assignment_id)
        else:
            import uuid
            session_id = f"freeform_{uuid.uuid4().hex[:8]}"

    session = load_session(session_id)

    # Start with base state from request
    initial_state = {
        "mode": body.mode,
        "user_prompt": body.prompt,
        "course_id": body.course_id,
        "org_unit_id": body.org_unit_id,
        "course_name": body.course_name,
        "assignment_id": body.assignment_id,
        "assignment_text": body.assignment_text,
        "assignment_attachments": body.assignment_attachments,
        "user_selected_topics": body.selected_topic_ids,
        "uploaded_files": body.uploaded_files,
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

    async def event_generator():
        last_state = initial_state.copy()
        yield f"data: {json.dumps({'type': 'progress', 'node': 'Starting pipeline...'})}\n\n"

        async for state in graph.astream(initial_state, stream_mode="values"):
            last_state = state
            
            plog = state.get("pipeline_log", [])
            node_name = "Processing..."
            if plog and len(plog) > 0:
                node_name = plog[-1].get("node", "Processing...")
                
            yield f"data: {json.dumps({'type': 'progress', 'node': node_name})}\n\n"

        # After stream completes, persist the final state
        response_text = last_state.get("response", "")
        append_turn(session_id, body.prompt, response_text)
        cache_pipeline_state(session_id, last_state)

        final_payload = {
            "type": "result",
            "response": response_text,
            "context_mode": last_state.get("context_mode"),
            "retrieval_queries": last_state.get("retrieval_queries", []),
            "inaccessible_topics": last_state.get("inaccessible_topics", []),
            "too_long_videos": last_state.get("too_long_videos", []),
            "task_plan": last_state.get("task_plan", []),
            "session_id": session_id,
            "pipeline_log": last_state.get("pipeline_log", [])
        }
        yield f"data: {json.dumps(final_payload)}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.delete("/sessions/id/{session_id}")
async def clear_session_by_id(session_id: str):
    delete_session(session_id)
    return {"status": "ok"}


@router.delete("/sessions/{course_id}/{assignment_id}")
async def clear_session(course_id: int, assignment_id: int):
    session_id = build_session_id(course_id, assignment_id)
    deleted = delete_session(session_id)
    return {"deleted": deleted, "session_id": session_id}


@router.delete("/sessions")
async def clear_all_sessions():
    count = delete_all_sessions()
    return {"deleted_count": count}


class TodoUpdateRequest(BaseModel):
    todos: list[dict]


@router.get("/sessions/{session_id}/todos")
async def get_todos(session_id: str, token: str = Depends(get_bs_token)):
    """Fetch the current to-do list for a session."""
    plan = get_task_plan(session_id)
    if plan is None:
        return {"todos": [], "found": False}
    return {"todos": plan, "found": True}


@router.patch("/sessions/{session_id}/todos")
async def patch_todos(session_id: str, body: TodoUpdateRequest, token: str = Depends(get_bs_token)):
    """Update the full to-do list for a session."""
    from fastapi import HTTPException
    success = update_task_plan(session_id, body.todos)
    if not success:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "ok", "count": len(body.todos)}
