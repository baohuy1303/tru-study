"""Node 3: Material Reference Extractor.

Parses assignment text to identify referenced course materials
(slides, chapters, readings, papers, etc.) using LLM structured output.
"""

import os
from dotenv import load_dotenv
from pydantic import BaseModel
from langchain_openai import ChatOpenAI

from agents.state import GraphState

load_dotenv()


class MaterialReference(BaseModel):
    name: str           # e.g. "Chapter 5", "Week 3 Slides", "Normalization Reading"
    material_type: str  # "chapter", "slides", "paper", "video", "lab", "other"
    context_hint: str   # Surrounding sentence for fuzzy matching context


class ExtractedReferences(BaseModel):
    references: list[MaterialReference]


_llm = None


def _get_llm() -> ChatOpenAI:
    global _llm
    if _llm is None:
        _llm = ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-4o"),
            temperature=0,
        )
    return _llm


SYSTEM_PROMPT = """You are analyzing a university assignment to identify all referenced course materials.

Scan the text for BOTH:
1. Explicit references: "see Chapter 5", "refer to Lecture 3 slides", "Appendix B", "use the template from Week 2"
2. Implicit references: "as discussed in class regarding normalization", "from the reading on distributed systems", "the formula covered in lecture"

For each reference found, extract:
- name: The most specific identifier you can find (e.g. "Chapter 5", "Week 3 Slides", "Normalization Reading")
- material_type: One of "chapter", "slides", "paper", "video", "lab", "textbook", "other"
- context_hint: The full sentence or phrase where this reference appears (this helps match against actual file names later)

If no course materials are referenced, return an empty list. Do NOT hallucinate references that aren't in the text."""


def material_extractor(state: GraphState) -> dict:
    """Extract material references from assignment text using structured LLM output."""
    import time
    from utils.pipeline_log import log_step
    
    t0 = time.time()
    # Skip if references already cached (multi-turn)
    if state.get("material_references") is not None:
        print("[material_extractor] Skipping -- references already cached")
        return {"pipeline_log": log_step(state, "material_extractor", "skipped", "references already cached", time.time() - t0)}

    text = state.get("assignment_text", "")

    if not text.strip():
        return {"material_references": [], "pipeline_log": log_step(state, "material_extractor", "done", "no text", time.time() - t0)}

    try:
        llm = _get_llm()
        structured_llm = llm.with_structured_output(ExtractedReferences)

        result = structured_llm.invoke([
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ])

        refs = [ref.model_dump() for ref in result.references]
        if refs:
            print(f"[material_extractor] Found {len(refs)} material references")
            for r in refs:
                print(f"  - {r['name']} ({r['material_type']})")
        else:
            print("[material_extractor] No material references found in assignment text")
            
        elapsed = time.time() - t0

        return {"material_references": refs, "pipeline_log": log_step(state, "material_extractor", "done", f"found {len(refs)} references", elapsed)}

    except Exception as e:
        print(f"[material_extractor] LLM extraction failed: {e}")
        return {"material_references": [], "pipeline_log": log_step(state, "material_extractor", "error", str(e), time.time() - t0)}
