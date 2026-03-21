"""Node 1: PDF Parser & Token Evaluator.

Extracts text from assignment PDF (or uses provided text), counts tokens.
"""

from agents.state import GraphState
from utils.tokens import count_tokens


def pdf_parser(state: GraphState) -> dict:
    """Extract assignment text and count tokens.

    If assignment_text is already provided (e.g. from Brightspace instructions),
    skip PDF parsing and just count tokens. If assignment_pdf_path is set,
    parse the PDF to extract text.
    """
    text = state.get("assignment_text") or ""

    # TODO (Phase 2): If assignment_pdf_path is set and text is empty,
    # parse PDF with pymupdf and extract clean text.

    token_count = count_tokens(text) if text else 0

    return {
        "assignment_text": text,
        "assignment_token_count": token_count,
    }
