"""
Planner Agent
=============
Given a research topic, this node produces:
  • A written research plan
  • A list of ResearchThread objects (thematic clusters)
  • Prioritised ResearchQuery objects within each thread

Uses structured output via a Pydantic-backed prompt chain.
"""
from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from schemas import ResearchState, ResearchThread, ResearchQuery
from llm import get_llm
from logger import print_phase, print_info, print_success

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt
# ---------------------------------------------------------------------------

PLANNER_SYSTEM = """You are an expert research strategist. Your job is to decompose a research topic
into a structured investigation plan.

You must respond ONLY with valid JSON — no markdown fences, no preamble.

The JSON schema is:
{
  "research_plan": "<2-3 paragraph overview of the research strategy>",
  "threads": [
    {
      "theme": "<thematic cluster name>",
      "queries": [
        {
          "query": "<specific search query>",
          "rationale": "<why this query matters>",
          "priority": <1-5, 1=highest>
        }
      ]
    }
  ]
}

Guidelines:
- Create 3-5 thematic threads that cover the topic from different angles.
- Each thread should have 2-4 specific, search-engine-ready queries.
- Queries should be diverse: factual, analytical, historical, current, critical.
- Prioritise queries that will surface conflicting viewpoints or evidence gaps.
- Priority 1 = most important to answer first.
"""


def run_planner(state: ResearchState) -> ResearchState:
    """LangGraph node: creates the research plan."""
    print_phase("planning", f"Topic: {state.topic}")

    llm = get_llm()
    messages = [
        SystemMessage(content=PLANNER_SYSTEM),
        HumanMessage(content=(
            f"Research topic: {state.topic}\n\n"
            f"Research depth requested: {state.research_depth} "
            f"(1=shallow, 4=exhaustive)\n\n"
            "Produce a comprehensive research plan."
        )),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()

        # Strip markdown fences if the model wraps anyway
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()

        data = json.loads(raw)
        state.research_plan = data.get("research_plan", "")

        threads: List[ResearchThread] = []
        for td in data.get("threads", []):
            queries = [
                ResearchQuery(
                    query=q["query"],
                    rationale=q.get("rationale", ""),
                    priority=int(q.get("priority", 3)),
                )
                for q in td.get("queries", [])
            ]
            thread = ResearchThread(theme=td["theme"], queries=queries)
            threads.append(thread)

        state.threads = threads
        state.all_queries = [q for t in threads for q in t.queries]

        print_success(f"Plan created: {len(threads)} threads, "
                      f"{len(state.all_queries)} queries")
        for t in threads:
            print_info(f"Thread: {t.theme} ({len(t.queries)} queries)")

    except Exception as e:
        logger.error(f"Planner failed: {e}")
        state.errors.append(f"Planner error: {e}")
        # Fallback: one generic thread
        fallback = ResearchThread(
            theme="General Research",
            queries=[ResearchQuery(query=state.topic, priority=1)],
        )
        state.threads = [fallback]
        state.all_queries = fallback.queries

    state.status = "researching"
    return state
