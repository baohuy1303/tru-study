"""Node 3: Material Reference Extractor.

Parses assignment text to identify referenced course materials
(slides, chapters, readings, papers, etc.) using structured LLM output.
"""

from agents.state import GraphState


def material_extractor(state: GraphState) -> dict:
    """Extract material references from assignment text.

    Uses LLM with structured output to identify both explicit references
    ("see Chapter 5") and implicit ones ("as discussed in class").
    """
    # TODO (Phase 3): Use langchain with_structured_output to extract
    # MaterialReference objects from assignment_text.
    return {
        "material_references": [],
    }
