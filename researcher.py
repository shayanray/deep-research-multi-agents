"""
Researcher Agent
================
Executes all pending research queries, gathers sources from multiple
tools (web, Wikipedia, arXiv), and optionally generates follow-up
queries when evidence gaps are detected.
"""
from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from schemas import (
    ResearchState, ResearchQuery, Source, Evidence, ResearchThread,
)
from search_tools import multi_source_search
from llm import get_llm, get_fast_llm
from logger import print_phase, print_info, print_success, print_source_table

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

EVIDENCE_EXTRACTOR_SYSTEM = """You are a research analyst. Given a search query and retrieved source content,
extract key claims and evidence.

Respond ONLY with valid JSON (no fences):
{
  "evidence": [
    {
      "claim": "<factual claim found in the sources>",
      "confidence": <0.0-1.0>,
      "supporting_source_indices": [<0-based indices of sources that support this>],
      "conflicting_source_indices": [<0-based indices of contradicting sources>]
    }
  ],
  "evidence_gaps": ["<question that remains unanswered>"],
  "follow_up_queries": [
    {"query": "<follow-up search query>", "rationale": "<why>", "priority": <1-5>}
  ]
}

Extract 2-6 distinct, concrete claims. Note evidence gaps. Suggest 0-2 follow-up queries only if critical.
"""

FOLLOW_UP_THRESHOLD = 2   # Only add follow-ups when iteration < this number


def _extract_evidence(
    query: str,
    sources: List[Source],
    current_iteration: int,
    llm,
) -> tuple[List[Evidence], List[ResearchQuery]]:
    """Ask the LLM to extract evidence and optional follow-up queries."""
    if not sources:
        return [], []

    source_texts = "\n\n".join(
        f"[{i}] {s.title}\nURL: {s.url}\n{s.content[:800]}"
        for i, s in enumerate(sources)
    )

    messages = [
        SystemMessage(content=EVIDENCE_EXTRACTOR_SYSTEM),
        HumanMessage(content=(
            f"Research query: {query}\n\n"
            f"Sources:\n{source_texts}"
        )),
    ]

    try:
        response = llm.invoke(messages)
        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        data = json.loads(raw)

        evidences: List[Evidence] = []
        for e in data.get("evidence", []):
            sup = [sources[i].id for i in e.get("supporting_source_indices", [])
                   if i < len(sources)]
            con = [sources[i].id for i in e.get("conflicting_source_indices", [])
                   if i < len(sources)]
            evidences.append(Evidence(
                claim=e["claim"],
                confidence=float(e.get("confidence", 0.5)),
                supporting_sources=sup,
                conflicting_sources=con,
            ))

        follow_ups: List[ResearchQuery] = []
        if current_iteration < FOLLOW_UP_THRESHOLD:
            for fq in data.get("follow_up_queries", [])[:2]:
                follow_ups.append(ResearchQuery(
                    query=fq["query"],
                    rationale=fq.get("rationale", ""),
                    priority=int(fq.get("priority", 3)),
                    depth=current_iteration + 1,
                ))

        return evidences, follow_ups

    except Exception as e:
        logger.warning(f"Evidence extraction failed: {e}")
        return [], []


# ---------------------------------------------------------------------------
# Main researcher node
# ---------------------------------------------------------------------------

def run_researcher(state: ResearchState) -> ResearchState:
    """LangGraph node: execute queries and gather evidence."""
    print_phase("researching",
                f"Iteration {state.current_iteration + 1}/{state.research_depth}")

    fast_llm = get_fast_llm()
    new_sources_count = 0
    new_follow_ups: List[ResearchQuery] = []

    # Gather pending queries (respect priority order)
    pending = sorted(
        [q for q in state.all_queries if q.status == "pending"],
        key=lambda q: q.priority,
    )

    print_info(f"Running {len(pending)} pending queries…")

    for query in pending:
        query.status = "in_progress"
        print_info(f"  🔍  {query.query[:70]}")

        try:
            sources = multi_source_search(
                query.query,
                max_results=state.max_sources_per_query,
                include_web=True,
                include_wiki=True,
                include_arxiv=state.current_iteration == 0,  # arxiv on first pass
            )

            # Merge into global source store
            for s in sources:
                if s.id not in state.all_sources:
                    state.all_sources[s.id] = s
                    new_sources_count += 1

            # Extract evidence
            evidences, follow_ups = _extract_evidence(
                query.query,
                sources,
                state.current_iteration,
                fast_llm,
            )
            state.all_evidence.extend(evidences)
            new_follow_ups.extend(follow_ups)
            query.status = "completed"

        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            state.errors.append(f"Query '{query.query[:50]}': {e}")
            query.status = "failed"

    # Add follow-up queries as a new thread if any
    if new_follow_ups:
        follow_up_thread = ResearchThread(
            theme=f"Follow-up Research (Iteration {state.current_iteration + 1})",
            queries=new_follow_ups,
            iteration=state.current_iteration + 1,
        )
        state.threads.append(follow_up_thread)
        state.all_queries.extend(new_follow_ups)
        print_info(f"Added {len(new_follow_ups)} follow-up queries for next iteration")

    state.current_iteration += 1

    print_success(f"Gathered {new_sources_count} new sources, "
                  f"{len(state.all_evidence)} total evidence items")
    print_source_table(list(state.all_sources.values())[-10:])

    # Decide next status
    still_pending = any(q.status == "pending" for q in state.all_queries)
    if still_pending and state.current_iteration < state.research_depth:
        state.status = "researching"          # loop back
    else:
        state.status = "analyzing"

    iteration_note = (
        f"Iteration {state.current_iteration}: "
        f"{new_sources_count} new sources, "
        f"{len(new_follow_ups)} follow-ups generated"
    )
    state.iteration_summaries.append(iteration_note)

    return state
