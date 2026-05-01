"""
Conflict Analyzer Agent
=======================
Identifies contradictions between gathered evidence, attempts to resolve
them, and records each conflict with a resolution strategy.
"""
from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from schemas import ResearchState, ConflictRecord, Evidence
from llm import get_llm
from logger import print_phase, print_info, print_conflicts

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

CONFLICT_DETECTION_SYSTEM = """You are a critical research analyst specializing in identifying contradictions
and inconsistencies in research evidence.

Given a list of evidence claims, identify pairs that directly contradict each other.

Respond ONLY with valid JSON (no fences):
{
  "conflicts": [
    {
      "topic": "<what the conflict is about>",
      "claim_a": "<first claim>",
      "evidence_indices_a": [<indices from evidence list>],
      "claim_b": "<contradicting claim>",
      "evidence_indices_b": [<indices from evidence list>],
      "resolution": "<how to reconcile: e.g. different time periods, different contexts, methodological differences>",
      "resolution_confidence": <0.0-1.0>,
      "resolved": <true/false>
    }
  ]
}

Only report genuine contradictions (different conclusions about the same fact).
Differences in emphasis or scope are NOT conflicts.
Return an empty list if no real conflicts exist.
"""


# ---------------------------------------------------------------------------
# Main node
# ---------------------------------------------------------------------------

def run_conflict_analyzer(state: ResearchState) -> ResearchState:
    """LangGraph node: detect and attempt to resolve evidence conflicts."""
    print_phase("analyzing", "Checking for conflicting evidence…")

    evidences = state.all_evidence
    if len(evidences) < 2:
        print_info("Not enough evidence to detect conflicts — skipping")
        state.status = "synthesizing"
        return state

    llm = get_llm()

    # Build evidence summary (truncate to keep prompt manageable)
    evidence_text = "\n".join(
        f"[{i}] (confidence={e.confidence:.2f}) {e.claim}"
        for i, e in enumerate(evidences[:40])   # cap at 40 claims
    )

    messages = [
        SystemMessage(content=CONFLICT_DETECTION_SYSTEM),
        HumanMessage(content=(
            f"Research topic: {state.topic}\n\n"
            f"Evidence claims:\n{evidence_text}"
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

        conflicts: List[ConflictRecord] = []
        for c in data.get("conflicts", []):
            # Map indices → evidence items → source IDs
            idx_a: list = c.get("evidence_indices_a", [])
            idx_b: list = c.get("evidence_indices_b", [])

            source_ids_a = []
            for i in idx_a:
                if i < len(evidences):
                    source_ids_a.extend(evidences[i].supporting_sources)

            source_ids_b = []
            for i in idx_b:
                if i < len(evidences):
                    source_ids_b.extend(evidences[i].supporting_sources)

            conflicts.append(ConflictRecord(
                topic=c.get("topic", ""),
                claim_a=c.get("claim_a", ""),
                source_ids_a=list(set(source_ids_a)),
                claim_b=c.get("claim_b", ""),
                source_ids_b=list(set(source_ids_b)),
                resolution=c.get("resolution", ""),
                resolution_confidence=float(c.get("resolution_confidence", 0.0)),
                resolved=bool(c.get("resolved", False)),
            ))

        state.conflicts = conflicts
        print_info(f"Found {len(conflicts)} conflict(s)")
        print_conflicts(conflicts)

    except Exception as e:
        logger.warning(f"Conflict analysis failed: {e}")
        state.errors.append(f"Conflict analyzer error: {e}")

    state.status = "synthesizing"
    return state
