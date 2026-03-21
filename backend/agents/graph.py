"""LangGraph pipeline: multi-agent assignment helper.

Wires up all nodes with conditional routing based on token count.

Flow:
  pdf_parser → token_gate (conditional)
    ├── small → small_context_handler → material_extractor
    └── large → large_context_handler → material_extractor
  material_extractor → material_fetcher → query_rewriter → responder → END
"""

import os
from dotenv import load_dotenv
from langgraph.graph import StateGraph, END

from agents.state import GraphState
from agents.nodes.pdf_parser import pdf_parser
from agents.nodes.context_handler import handle_small_context, handle_large_context
from agents.nodes.material_extractor import material_extractor
from agents.nodes.material_fetcher import material_fetcher
from agents.nodes.query_rewriter import query_rewriter
from agents.nodes.responder import responder

load_dotenv()

TOKEN_THRESHOLD = int(os.getenv("TOKEN_THRESHOLD", "60000"))


def _token_gate(state: GraphState) -> str:
    """Route based on assignment token count."""
    count = state.get("assignment_token_count", 0)
    if count < TOKEN_THRESHOLD:
        return "small"
    return "large"


def build_graph() -> StateGraph:
    """Build and compile the LangGraph pipeline."""
    graph = StateGraph(GraphState)

    # Add nodes
    graph.add_node("pdf_parser", pdf_parser)
    graph.add_node("small_context_handler", handle_small_context)
    graph.add_node("large_context_handler", handle_large_context)
    graph.add_node("material_extractor", material_extractor)
    graph.add_node("material_fetcher", material_fetcher)
    graph.add_node("query_rewriter", query_rewriter)
    graph.add_node("responder", responder)

    # Set entry point
    graph.set_entry_point("pdf_parser")

    # Conditional routing after PDF parsing
    graph.add_conditional_edges(
        "pdf_parser",
        _token_gate,
        {
            "small": "small_context_handler",
            "large": "large_context_handler",
        },
    )

    # Both context handlers converge at material_extractor
    graph.add_edge("small_context_handler", "material_extractor")
    graph.add_edge("large_context_handler", "material_extractor")

    # Linear pipeline from material_extractor to END
    graph.add_edge("material_extractor", "material_fetcher")
    graph.add_edge("material_fetcher", "query_rewriter")
    graph.add_edge("query_rewriter", "responder")
    graph.add_edge("responder", END)

    return graph.compile()
