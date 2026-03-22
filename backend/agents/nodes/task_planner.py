"""Node: Task Planner.

Analyzes assignment text/summary to generate an actionable to-do checklist
of steps the student needs to complete. Only runs on first pipeline execution
for an assignment (skipped when cached).
"""

import os
import uuid

from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI

from agents.state import GraphState

load_dotenv()


class TodoItem(BaseModel):
    text: str


class TaskPlan(BaseModel):
    items: list[TodoItem]


_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=0.3,
        )
    return _llm


SYSTEM_PROMPT = """You are analyzing a university assignment to create a clear, actionable to-do checklist for the student.

Given the assignment text, break it down into specific, ordered steps that a student needs to complete. Each step should be:
1. Concrete and actionable (start with a verb: "Read...", "Write...", "Implement...", "Submit...")
2. Appropriately granular -- not too broad ("Do the assignment") and not too micro ("Open your text editor")
3. In logical completion order
4. Covering ALL deliverables, tasks, and submission requirements mentioned in the assignment

Include steps for:
- Reading/reviewing referenced materials
- Each distinct question or task in the assignment
- Creating required deliverables (code files, documents, diagrams)
- Following formatting/submission requirements
- Submitting the final work

Typically produce 5-15 items depending on assignment complexity. For simple assignments, fewer is better. For multi-part projects, more detail is appropriate.

Do NOT include vague steps like "Understand the assignment" or "Get started"."""


def task_planner(state: GraphState) -> dict:
    """Generate an actionable to-do list from assignment text."""
    import time
    from utils.pipeline_log import log_step

    t0 = time.time()

    # Skip if already cached (multi-turn)
    if state.get("task_plan"):
        print("[task_planner] Skipping -- task plan already cached")
        return {"pipeline_log": log_step(state, "task_planner", "skipped", "cached", time.time() - t0)}

    # Only generate for assignments (not freeform)
    assignment_id = state.get("assignment_id")
    if not assignment_id:
        print("[task_planner] Skipping -- no assignment_id (freeform mode)")
        return {"pipeline_log": log_step(state, "task_planner", "skipped", "freeform", time.time() - t0)}

    # Use summary if available, otherwise raw text
    text = state.get("assignment_summary") or state.get("assignment_text", "")
    if not text.strip():
        return {"task_plan": [], "pipeline_log": log_step(state, "task_planner", "done", "no text", time.time() - t0)}

    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(TaskPlan)

        result = structured_llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ])

        plan = [
            {
                "id": uuid.uuid4().hex[:8],
                "text": item.text,
                "completed": False,
                "order": i,
            }
            for i, item in enumerate(result.items)
        ]

        print(f"[task_planner] Generated {len(plan)} to-do items")
        for item in plan:
            print(f"  - {item['text']}")

        elapsed = time.time() - t0
        return {
            "task_plan": plan,
            "pipeline_log": log_step(state, "task_planner", "done", f"{len(plan)} items", elapsed),
        }

    except Exception as e:
        print(f"[task_planner] LLM generation failed: {e}")
        return {
            "task_plan": [],
            "pipeline_log": log_step(state, "task_planner", "error", str(e), time.time() - t0),
        }
