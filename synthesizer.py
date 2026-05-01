"""
Synthesizer Agent
=================
Cross-thread synthesis: combines evidence from all research threads,
weighs conflicting information, and produces:
  • Consolidated key findings
  • Synthesis narrative
  • Confidence assessment
"""
from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from schemas import ResearchState
from llm import get_llm
from logger import print_phase, print_info, print_success

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYNTHESIZER_SYSTEM = """You are a senior research analyst synthesizing findings across multiple evidence threads.

Your job is to:
1. Identify the most well-supported conclusions
2. Note where evidence is weak or contested
3. Connect findings across different research angles
4. Assess overall confidence in what is known

Respond ONLY with valid JSON (no fences):
{
  "key_findings": [
    "<concrete, specific finding supported by evidence>",
    ...
  ],
  "synthesis_narrative": "<3-5 paragraph narrative synthesizing ALL evidence across threads>",
  "confidence_score": <0.0-1.0 overall evidence quality>,
  "knowledge_gaps": ["<important unanswered question>"],
  "methodological_notes": "<notes on source quality, diversity, limitations>"
}

Rules:
- Key findings should be 5-10 specific, evidence-backed statements.
- Synthesis narrative must acknowledge contradictions and uncertainties.
- Confidence score: 0.9+ only if evidence is abundant, diverse, and consistent.
- Be intellectually honest about what the evidence does NOT support.
"""


def run_synthesizer(state: ResearchState) -> ResearchState:
    """LangGraph node: synthesize evidence across all threads."""
    print_phase("synthesizing", "Cross-thread synthesis…")

    llm = get_llm()

    # Prepare compact evidence summary
    evidence_lines = [
        f"• [{e.confidence:.2f}] {e.claim}"
        for e in sorted(state.all_evidence, key=lambda x: -x.confidence)[:50]
    ]
    evidence_text = "\n".join(evidence_lines) if evidence_lines else "No evidence gathered."

    # Thread summaries
    thread_summaries = "\n".join(
        f"Thread '{t.theme}': {len(t.queries)} queries, status={t.status}"
        for t in state.threads
    )

    # Conflict summary
    conflict_lines = []
    for c in state.conflicts:
        status = "✓ resolved" if c.resolved else "✗ unresolved"
        conflict_lines.append(
            f"• [{status}] {c.topic}: {c.claim_a[:60]} vs {c.claim_b[:60]}"
        )
    conflict_text = "\n".join(conflict_lines) if conflict_lines else "No conflicts detected."

    messages = [
        SystemMessage(content=SYNTHESIZER_SYSTEM),
        HumanMessage(content=(
            f"Research topic: {state.topic}\n\n"
            f"Research threads:\n{thread_summaries}\n\n"
            f"Key evidence (sorted by confidence):\n{evidence_text}\n\n"
            f"Conflicts:\n{conflict_text}\n\n"
            f"Total sources: {len(state.all_sources)}\n"
            f"Research iterations: {state.current_iteration}"
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

        state.key_findings = data.get("key_findings", [])
        state.synthesis_notes = data.get("synthesis_narrative", "")

        # Store confidence in a temporary attribute (used by report writer)
        state.__dict__["_confidence"] = float(data.get("confidence_score", 0.5))
        state.__dict__["_knowledge_gaps"] = data.get("knowledge_gaps", [])
        state.__dict__["_methodological_notes"] = data.get("methodological_notes", "")

        print_success(
            f"Synthesis complete: {len(state.key_findings)} key findings, "
            f"confidence={state.__dict__.get('_confidence', 0):.2f}"
        )
        for f in state.key_findings[:5]:
            print_info(f"  • {f[:90]}")

    except Exception as e:
        logger.error(f"Synthesizer failed: {e}")
        state.errors.append(f"Synthesizer error: {e}")
        state.key_findings = [
            f"Research gathered {len(state.all_sources)} sources on {state.topic}"
        ]
        state.synthesis_notes = "Automated synthesis failed; see raw evidence."

    state.status = "writing"
    return state
