"""Session persistence for multi-turn chat conversations.

Sessions are scoped by assignment: session_id = "{course_id}_{assignment_id}".
Stores chat history and cached pipeline state so subsequent turns skip expensive work.
"""

import json
import os

_SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", "storage", "sessions")

# Fields from GraphState that are safe to cache across turns
_CACHEABLE_FIELDS = [
    "assignment_text",
    "assignment_token_count",
    "context_mode",
    "assignment_summary",
    "assignment_embedded",
    "material_references",
    "embedded_materials",
    "task_plan",
]


def build_session_id(course_id: int, assignment_id: int | None) -> str:
    """Build a session ID from course and assignment IDs."""
    if assignment_id:
        return f"{course_id}_{assignment_id}"
    return f"{course_id}_general"


def _session_path(session_id: str) -> str:
    os.makedirs(_SESSION_DIR, exist_ok=True)
    return os.path.join(_SESSION_DIR, f"{session_id}.json")


def load_session(session_id: str) -> dict | None:
    """Load a session from disk. Returns None if not found."""
    path = _session_path(session_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def save_session(session_id: str, data: dict) -> None:
    """Write session data to disk."""
    path = _session_path(session_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def append_turn(session_id: str, user_msg: str, assistant_msg: str) -> None:
    """Append a user + assistant turn to the session's chat history."""
    session = load_session(session_id) or {"session_id": session_id, "chat_history": [], "cached_state": {}}
    session["chat_history"].append({"role": "user", "content": user_msg})
    session["chat_history"].append({"role": "assistant", "content": assistant_msg})
    save_session(session_id, session)


def cache_pipeline_state(session_id: str, state: dict) -> None:
    """Extract cacheable fields from pipeline state and save to session."""
    session = load_session(session_id) or {"session_id": session_id, "chat_history": [], "cached_state": {}}
    cached = {}
    for field in _CACHEABLE_FIELDS:
        if field in state and state[field] is not None:
            cached[field] = state[field]
    session["cached_state"] = cached
    save_session(session_id, session)


def get_task_plan(session_id: str) -> list[dict] | None:
    """Retrieve the task plan from a session. Returns None if session not found."""
    session = load_session(session_id)
    if not session:
        return None
    return session.get("cached_state", {}).get("task_plan")


def update_task_plan(session_id: str, task_plan: list[dict]) -> bool:
    """Update the task plan in a session's cached state. Returns True if session exists."""
    session = load_session(session_id)
    if not session:
        return False
    if "cached_state" not in session:
        session["cached_state"] = {}
    session["cached_state"]["task_plan"] = task_plan
    save_session(session_id, session)
    return True


def delete_session(session_id: str) -> bool:
    """Delete a single session file. Returns True if deleted, False if not found."""
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False


def delete_all_sessions() -> int:
    """Delete all session JSON files. Returns count of deleted files."""
    if not os.path.exists(_SESSION_DIR):
        return 0
    count = 0
    for fname in os.listdir(_SESSION_DIR):
        if fname.endswith(".json"):
            try:
                os.remove(os.path.join(_SESSION_DIR, fname))
                count += 1
            except OSError:
                pass
    return count
