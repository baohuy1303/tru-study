"""POST /api/chat — Entry point for the LangGraph multi-agent pipeline."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from dependencies import get_bs_token
from agents.graph import build_graph

router = APIRouter(prefix="/api")


class ChatRequest(BaseModel):
    prompt: str
    course_id: int
    org_unit_id: int
    assignment_id: int | None = None
    assignment_text: str | None = None  # Instructions text from frontend
    chat_history: list[dict] = []


@router.post("/chat")
async def chat(body: ChatRequest, token: str = Depends(get_bs_token)):
    graph = build_graph()

    initial_state = {
        "user_prompt": body.prompt,
        "chat_history": body.chat_history,
        "course_id": body.course_id,
        "org_unit_id": body.org_unit_id,
        "assignment_text": body.assignment_text,
        "bs_token": token,
    }

    result = await graph.ainvoke(initial_state)

    return {
        "response": result.get("response", ""),
        "context_mode": result.get("context_mode"),
        "retrieval_queries": result.get("retrieval_queries", []),
    }
