"""ChromaDB client singleton and collection helpers."""

import os
import chromadb

_CHROMA_DIR = os.path.join(os.path.dirname(__file__), "..", "storage", "chroma")
_client = None


def get_chroma_client() -> chromadb.ClientAPI:
    """Return a persistent ChromaDB client (singleton)."""
    global _client
    if _client is None:
        os.makedirs(_CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(path=_CHROMA_DIR)
    return _client


def get_course_materials_collection(course_id: int):
    """Get or create the course materials collection for a given course."""
    client = get_chroma_client()
    return client.get_or_create_collection(name=f"course_materials_{course_id}")


def get_assignment_collection(assignment_id: int):
    """Get or create the assignment collection for a given assignment."""
    client = get_chroma_client()
    return client.get_or_create_collection(name=f"assignment_{assignment_id}")
