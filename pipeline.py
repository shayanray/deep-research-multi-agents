"""
LangGraph Pipeline
==================
Wires all agent nodes into a directed graph with conditional routing:

  [planner]
      │
      ▼
  [researcher]  ◄──── loops while pending queries & iterations remain
      │
      ▼ (when done)
  [conflict_analyzer]
      │
      ▼
  [synthesizer]
      │
      ▼
  [report_writer]
      │
      ▼
   [END]

The researcher loops back to itself when there are still pending queries
and we haven't exceeded research_depth iterations.
"""
from __future__ import annotations

import logging
from typing import Any

from langgraph.graph import StateGraph, END

from schemas import ResearchState
from planner import run_planner
from researcher import run_researcher
from conflict_analyzer import run_conflict_analyzer
from synthesizer import run_synthesizer
from report_writer import run_report_writer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Node wrappers (LangGraph expects dict in / dict out)
# ---------------------------------------------------------------------------

def _to_dict(state: ResearchState) -> dict:
    return state.model_dump()


def _from_dict(d: dict) -> ResearchState:
    return ResearchState(**d)


def planner_node(state_dict: dict) -> dict:
    state = _from_dict(state_dict)
    return _to_dict(run_planner(state))


def researcher_node(state_dict: dict) -> dict:
    state = _from_dict(state_dict)
    return _to_dict(run_researcher(state))


def conflict_node(state_dict: dict) -> dict:
    state = _from_dict(state_dict)
    return _to_dict(run_conflict_analyzer(state))


def synthesizer_node(state_dict: dict) -> dict:
    state = _from_dict(state_dict)
    return _to_dict(run_synthesizer(state))


def report_writer_node(state_dict: dict) -> dict:
    state = _from_dict(state_dict)
    return _to_dict(run_report_writer(state))


# ---------------------------------------------------------------------------
# Routing logic
# ---------------------------------------------------------------------------

def researcher_router(state_dict: dict) -> str:
    """After researcher runs: loop back or move to analysis."""
    status = state_dict.get("status", "")
    if status == "researching":
        return "researcher"
    return "conflict_analyzer"


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    graph = StateGraph(dict)

    graph.add_node("planner", planner_node)
    graph.add_node("researcher", researcher_node)
    graph.add_node("conflict_analyzer", conflict_node)
    graph.add_node("synthesizer", synthesizer_node)
    graph.add_node("report_writer", report_writer_node)

    graph.set_entry_point("planner")

    graph.add_edge("planner", "researcher")
    graph.add_conditional_edges(
        "researcher",
        researcher_router,
        {
            "researcher": "researcher",
            "conflict_analyzer": "conflict_analyzer",
        },
    )
    graph.add_edge("conflict_analyzer", "synthesizer")
    graph.add_edge("synthesizer", "report_writer")
    graph.add_edge("report_writer", END)

    return graph


def get_compiled_graph():
    return build_graph().compile()
