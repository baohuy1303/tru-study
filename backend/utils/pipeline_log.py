"""Structured pipeline step logger for frontend consumption."""


def log_step(state: dict, node: str, status: str, detail: str = "", duration_s: float = 0) -> list[dict]:
    """Append a pipeline step log entry and return updated log list.

    Status values: "done", "skipped", "error", "warning"
    """
    log = list(state.get("pipeline_log") or [])
    log.append({
        "node": node,
        "status": status,
        "detail": detail,
        "duration_s": round(duration_s, 2),
    })
    return log
