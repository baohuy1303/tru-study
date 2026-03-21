"""Smoke tests for the LangGraph pipeline (Phase 1 + Phase 2).

Run: python test_graph.py
     python test_graph.py --with-llm   (requires OPENAI_API_KEY)
"""

import os
import sys
import pymupdf

from agents.graph import build_graph
from utils.chroma import get_assignment_collection, get_chroma_client

USE_LLM = "--with-llm" in sys.argv


# ── Phase 1 tests (no API key needed) ────────────────────────────────────────

def test_small_context_path():
    """Short assignment routes through inject path."""
    graph = build_graph()
    result = graph.invoke({
        "user_prompt": "Help me with this assignment",
        "chat_history": [],
        "course_id": 123,
        "org_unit_id": 456,
        "course_name": "CS 101",
        "assignment_text": "Write a 500-word essay on database normalization.",
        "bs_token": "test-token",
    })

    assert result["context_mode"] == "inject", f"Expected 'inject', got '{result['context_mode']}'"
    assert result["assignment_token_count"] < 4000
    assert result["response"], "Response should not be empty"
    print(f"[PASS] Small context path — {result['assignment_token_count']} tokens, mode={result['context_mode']}")


def test_large_context_path():
    """Long assignment routes through RAG path."""
    graph = build_graph()
    long_text = "This is a detailed assignment instruction about data structures and algorithms. " * 2000

    result = graph.invoke({
        "user_prompt": "Summarize this assignment",
        "chat_history": [],
        "course_id": 789,
        "org_unit_id": 101,
        "course_name": "CS 310",
        "assignment_id": 99999,
        "assignment_text": long_text,
        "bs_token": "test-token",
    })

    assert result["context_mode"] == "rag", f"Expected 'rag', got '{result['context_mode']}'"
    assert result["assignment_token_count"] >= 4000
    print(f"[PASS] Large context path — {result['assignment_token_count']} tokens, mode={result['context_mode']}")

    if USE_LLM:
        assert result["assignment_embedded"] is True, "Should have embedded chunks into Chroma"
        collection = get_assignment_collection(99999)
        count = collection.count()
        assert count > 0, f"Expected chunks in Chroma, got {count}"
        print(f"       Chroma chunks: {count}")
        print(f"       Summary: {result['assignment_summary'][:150]}...")

        # Cleanup test collection
        client = get_chroma_client()
        client.delete_collection("assignment_99999")


def test_empty_input():
    """No text, no PDF — pipeline handles gracefully."""
    graph = build_graph()
    result = graph.invoke({
        "user_prompt": "Hello",
        "chat_history": [],
        "course_id": 1,
        "org_unit_id": 1,
        "course_name": "General",
        "bs_token": "test-token",
    })

    assert result["context_mode"] == "inject", "Empty text should route to small/inject"
    assert result["assignment_token_count"] == 0
    print(f"[PASS] Empty input — {result['assignment_token_count']} tokens, mode={result['context_mode']}")


# ── Phase 2 tests ────────────────────────────────────────────────────────────

def test_pdf_extraction():
    """Create a PDF in memory, pass as assignment_pdf_path, verify extraction."""
    # Create a simple test PDF
    test_pdf_path = os.path.join(os.path.dirname(__file__), "storage", "test_output.pdf")
    os.makedirs(os.path.dirname(test_pdf_path), exist_ok=True)

    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text(
        (72, 72),
        "CS 310 Assignment 3: Implement a Binary Search Tree\n\n"
        "Requirements:\n"
        "1. Implement insert, delete, and search operations\n"
        "2. Handle edge cases (empty tree, duplicate keys)\n"
        "3. Write unit tests for each operation\n"
        "4. Submit your code as a .zip file by Friday\n\n"
        "Grading: 40pts correctness, 30pts tests, 30pts style",
        fontsize=11,
    )
    doc.save(test_pdf_path)
    doc.close()

    graph = build_graph()
    result = graph.invoke({
        "user_prompt": "What are the requirements?",
        "chat_history": [],
        "course_id": 310,
        "org_unit_id": 500,
        "course_name": "CS 310 Data Structures",
        "assignment_pdf_path": test_pdf_path,
        "bs_token": "test-token",
    })

    assert result["assignment_token_count"] > 0, "Should have extracted text from PDF"
    assert "Binary Search Tree" in result["assignment_text"], "Should contain PDF content"
    print(f"[PASS] PDF extraction — {result['assignment_token_count']} tokens extracted")
    print(f"       Text preview: {result['assignment_text'][:100]}...")

    # Cleanup
    os.remove(test_pdf_path)


def test_small_summary_llm():
    """Verify real LLM summary generation for small context (requires OPENAI_API_KEY)."""
    if not USE_LLM:
        print("[SKIP] test_small_summary_llm — run with --with-llm")
        return

    graph = build_graph()
    result = graph.invoke({
        "user_prompt": "Help me understand this assignment",
        "chat_history": [],
        "course_id": 200,
        "org_unit_id": 300,
        "course_name": "CS 180 Intro to Programming",
        "assignment_text": (
            "Assignment 2: Loops and Functions\n\n"
            "Write a Python program that:\n"
            "1. Asks the user for a positive integer n\n"
            "2. Prints a multiplication table from 1 to n\n"
            "3. Defines a function is_prime(x) that returns True if x is prime\n"
            "4. Uses is_prime to print all primes up to n\n\n"
            "Grading (100 points):\n"
            "- Multiplication table: 30 pts\n"
            "- is_prime function: 40 pts\n"
            "- Prime listing: 20 pts\n"
            "- Code style and comments: 10 pts\n\n"
            "Due: Friday March 28 at 11:59 PM\n"
            "Submit via Brightspace dropbox as a single .py file"
        ),
        "bs_token": "test-token",
    })

    summary = result.get("assignment_summary", "")
    assert "placeholder" not in summary.lower(), "Summary should be real LLM output, not placeholder"
    assert len(summary) > 100, f"Summary too short: {len(summary)} chars"
    assert result["context_mode"] == "inject"
    print(f"[PASS] Small summary (LLM) — {len(summary)} chars, mode={result['context_mode']}")
    print(f"       Summary:\n{summary[:300]}...")


def test_large_chunking_llm():
    """Verify chunking + embedding + summary for large context (requires OPENAI_API_KEY)."""
    if not USE_LLM:
        print("[SKIP] test_large_chunking_llm — run with --with-llm")
        return

    graph = build_graph()
    # Generate text that exceeds TOKEN_THRESHOLD (4000 tokens ~ 16000 chars)
    long_text = (
        "Part N: Advanced Database Query Optimization. "
        "In this section you will analyze query execution plans for complex SQL joins "
        "involving multiple tables with millions of rows. Consider indexing strategies, "
        "query hints, and the impact of data distribution on optimizer choices. "
        "Write a detailed report with benchmarks comparing at least 3 approaches. "
        "Include diagrams showing the execution plan tree for each approach. "
    ) * 200

    result = graph.invoke({
        "user_prompt": "Overview of this assignment",
        "chat_history": [],
        "course_id": 400,
        "org_unit_id": 600,
        "course_name": "CS 450 Database Systems",
        "assignment_id": 88888,
        "assignment_text": long_text,
        "bs_token": "test-token",
    })

    assert result["context_mode"] == "rag"
    assert result["assignment_embedded"] is True
    summary = result.get("assignment_summary", "")
    assert "placeholder" not in summary.lower()

    collection = get_assignment_collection(88888)
    count = collection.count()
    assert count > 0, f"Expected chunks in Chroma, got {count}"

    print(f"[PASS] Large chunking (LLM) — {result['assignment_token_count']} tokens, {count} chunks embedded")
    print(f"       Summary:\n{summary[:300]}...")

    # Cleanup
    client = get_chroma_client()
    client.delete_collection("assignment_88888")


# ── Phase 3+4 tests ──────────────────────────────────────────────────────────

def test_material_extraction():
    """Verify LLM extracts material references from assignment text (requires OPENAI_API_KEY)."""
    if not USE_LLM:
        print("[SKIP] test_material_extraction — run with --with-llm")
        return

    from agents.nodes.material_extractor import material_extractor

    state = {
        "assignment_text": (
            "Assignment 4: Relational Database Design\n\n"
            "Read Chapter 5 from the textbook before starting this assignment.\n"
            "Refer to the Week 3 Normalization Slides for examples of 1NF, 2NF, and 3NF.\n"
            "You may also find the ER Diagram Lab helpful for Part 2.\n"
            "Use the SQL template provided in the Week 4 Resources folder.\n\n"
            "Questions:\n"
            "1. Normalize the given schema to 3NF (see Appendix B in the textbook)\n"
            "2. Draw an ER diagram for the normalized schema\n"
            "3. Write SQL CREATE TABLE statements"
        ),
    }

    result = material_extractor(state)
    refs = result.get("material_references", [])

    assert len(refs) > 0, "Should have found material references"
    ref_names = [r["name"].lower() for r in refs]
    # Should find at least some of: Chapter 5, Week 3 Slides, ER Diagram Lab, SQL template
    found_any = any(
        "chapter" in n or "slide" in n or "lab" in n or "template" in n or "appendix" in n
        for n in ref_names
    )
    assert found_any, f"Expected recognizable references, got: {ref_names}"

    print(f"[PASS] Material extraction — found {len(refs)} references:")
    for r in refs:
        print(f"       - {r['name']} ({r['material_type']})")


def test_material_extraction_empty():
    """Assignment with no references returns empty list."""
    if not USE_LLM:
        print("[SKIP] test_material_extraction_empty — run with --with-llm")
        return

    from agents.nodes.material_extractor import material_extractor

    state = {
        "assignment_text": "Write a 500-word essay about your favorite hobby. No specific format required.",
    }

    result = material_extractor(state)
    refs = result.get("material_references", [])
    assert len(refs) == 0, f"Expected no references for self-contained assignment, got: {refs}"
    print("[PASS] Material extraction empty — no references found (expected)")


def test_fuzzy_matching():
    """Test fuzzy matching logic in isolation (no Brightspace API needed)."""
    from agents.nodes.material_fetcher import _fuzzy_match

    references = [
        {"name": "Chapter 5", "material_type": "chapter", "context_hint": "Read Chapter 5 from the textbook"},
        {"name": "Week 3 Normalization Slides", "material_type": "slides", "context_hint": "Refer to the Week 3 Normalization Slides"},
        {"name": "ER Diagram Lab", "material_type": "lab", "context_hint": "the ER Diagram Lab helpful for Part 2"},
    ]

    catalog = [
        {"id": 1, "title": "Chapter 5 - Relational Model.pdf", "topic_type": 1, "url": None, "module_path": "Textbook Chapters"},
        {"id": 2, "title": "Week 3 - Normalization Slides.pptx", "topic_type": 1, "url": None, "module_path": "Lectures"},
        {"id": 3, "title": "Lab 3 - ER Diagrams.pdf", "topic_type": 1, "url": None, "module_path": "Labs"},
        {"id": 4, "title": "Syllabus.pdf", "topic_type": 1, "url": None, "module_path": "Course Info"},
        {"id": 5, "title": "Week 1 - Introduction.pptx", "topic_type": 1, "url": None, "module_path": "Lectures"},
    ]

    matched = _fuzzy_match(references, catalog)
    matched_ids = {m["id"] for m in matched}

    # Should match Chapter 5, Week 3 slides, and ER Lab — but NOT syllabus or Week 1
    assert 1 in matched_ids, "Should match Chapter 5"
    assert 2 in matched_ids, "Should match Week 3 slides"
    assert 3 in matched_ids, "Should match ER Diagram Lab"
    assert 4 not in matched_ids, "Should NOT match Syllabus"
    assert 5 not in matched_ids, "Should NOT match Week 1"

    print(f"[PASS] Fuzzy matching — matched {len(matched)}/3 expected items:")
    for m in matched:
        print(f"       - '{m['matched_ref']}' -> '{m['title']}' (score={m['match_score']})")


if __name__ == "__main__":
    print("Testing LangGraph pipeline...\n")
    print("=== Phase 1 (no API key) ===")
    test_small_context_path()
    test_large_context_path()
    test_empty_input()
    print()
    print("=== Phase 2 ===")
    test_pdf_extraction()
    test_small_summary_llm()
    test_large_chunking_llm()
    print()
    print("=== Phase 3+4 ===")
    test_material_extraction()
    test_material_extraction_empty()
    test_fuzzy_matching()
    print("\n=== All tests done ===")
