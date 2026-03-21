"""JSON manifest loader/saver for tracking embedded materials."""

import json
import os

_MANIFEST_DIR = os.path.join(os.path.dirname(__file__), "..", "storage", "manifests")


def _manifest_path(course_id: int) -> str:
    os.makedirs(_MANIFEST_DIR, exist_ok=True)
    return os.path.join(_MANIFEST_DIR, f"{course_id}.json")


def load_manifest(course_id: int) -> dict:
    """Load the materials manifest for a course. Returns empty dict if not found."""
    path = _manifest_path(course_id)
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_manifest(course_id: int, data: dict) -> None:
    """Save the materials manifest for a course."""
    path = _manifest_path(course_id)
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    except (IOError, OSError) as e:
        print(f"[manifest] Failed to save manifest for course {course_id}: {e}")
