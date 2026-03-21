"""Smoke test for the LangGraph pipeline skeleton (Phase 1).

Run: python test_graph.py
"""

from agents.graph import build_graph


def test_small_context_path():
    """Test that a short assignment routes through the small context handler."""
    graph = build_graph()
    result = graph.invoke({
        "user_prompt": "Help me with this assignment",
        "chat_history": [],
        "course_id": 123,
        "org_unit_id": 456,
        "assignment_text": "Write a 500-word essay on database normalization.",
        "bs_token": "test-token",
    })

    assert result["context_mode"] == "inject", f"Expected 'inject', got '{result['context_mode']}'"
    assert result["assignment_token_count"] < 4000
    assert result["response"], "Response should not be empty"
    print(f"[PASS] Small context path — {result['assignment_token_count']} tokens, mode={result['context_mode']}")
    print(f"       Response: {result['response'][:100]}...")


def test_large_context_path():
    """Test that a long assignment routes through the large context handler."""
    graph = build_graph()
    # Generate text that exceeds TOKEN_THRESHOLD (4000 tokens ~ 16000 chars)
    long_text = "This is a detailed assignment instruction. " * 2000

    result = graph.invoke({
        "user_prompt": "Summarize this assignment",
        "chat_history": [],
        "course_id": 789,
        "org_unit_id": 101,
        "assignment_text": long_text,
        "bs_token": "test-token",
    })

    assert result["context_mode"] == "rag", f"Expected 'rag', got '{result['context_mode']}'"
    assert result["assignment_token_count"] >= 4000
    assert result["response"], "Response should not be empty"
    print(f"[PASS] Large context path — {result['assignment_token_count']} tokens, mode={result['context_mode']}")
    print(f"       Response: {result['response'][:100]}...")


def test_empty_input():
    """Test that the pipeline handles empty/no assignment text gracefully."""
    graph = build_graph()
    result = graph.invoke({
        "user_prompt": "Hello",
        "chat_history": [],
        "course_id": 1,
        "org_unit_id": 1,
        "bs_token": "test-token",
    })

    assert result["context_mode"] == "inject", "Empty text should route to small/inject"
    assert result["assignment_token_count"] == 0
    print(f"[PASS] Empty input — {result['assignment_token_count']} tokens, mode={result['context_mode']}")


if __name__ == "__main__":
    print("Testing LangGraph pipeline skeleton...\n")
    test_small_context_path()
    test_large_context_path()
    test_empty_input()
    print("\n=== All tests passed ===")
