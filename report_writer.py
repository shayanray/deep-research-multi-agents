"""
Report Writer Agent
===================
Produces the final structured ResearchReport from synthesized findings.

The report includes:
  • Executive summary
  • Themed sections (one per research thread)
  • Key findings
  • Methodology & limitations
  • Full source list
"""
from __future__ import annotations

import json
import logging
from typing import List

from langchain_core.messages import HumanMessage, SystemMessage

from schemas import (
    ResearchState, ResearchReport, ReportSection,
)
from llm import get_llm
from logger import print_phase, print_info, print_success

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

REPORT_WRITER_SYSTEM = """You are an expert research report writer. Produce a comprehensive, structured research report.

Respond ONLY with valid JSON (no fences).  Schema:
{
  "title": "<compelling report title>",
  "executive_summary": "<3-4 paragraph executive summary covering main findings, controversies, and implications>",
  "sections": [
    {
      "title": "<section title>",
      "content": "<2-4 paragraphs of analytical prose, citing evidence and acknowledging uncertainty>",
      "subsections": [
        {
          "title": "<subsection title>",
          "content": "<1-2 paragraphs>",
          "subsections": []
        }
      ]
    }
  ],
  "methodology": "<paragraph describing how research was conducted, sources used, and iterations>",
  "limitations": "<paragraph honestly describing what this research could NOT determine and why>"
}

Guidelines:
- Write in an authoritative but balanced academic-journalistic style.
- Each section should address a distinct thematic thread.
- Explicitly reference conflicting evidence where relevant.
- Do NOT fabricate citations or statistics not present in the evidence.
- The executive summary must be stand-alone readable.
- Suggest 4-6 thematic sections; avoid boilerplate filler.
"""


def run_report_writer(state: ResearchState) -> ResearchState:
    """LangGraph node: write the final research report."""
    print_phase("writing", "Composing research report…")

    llm = get_llm()

    # Prepare inputs
    findings_text = "\n".join(f"• {f}" for f in state.key_findings)

    conflict_text = ""
    if state.conflicts:
        lines = []
        for c in state.conflicts:
            status = "Resolved" if c.resolved else "Unresolved"
            lines.append(
                f"• [{status}] {c.topic}: {c.claim_a[:80]} "
                f"→ vs ← {c.claim_b[:80]}"
                + (f" | Resolution: {c.resolution[:80]}" if c.resolution else "")
            )
        conflict_text = "\n".join(lines)

    thread_text = "\n".join(
        f"Thread '{t.theme}': {t.summary or 'completed'}"
        for t in state.threads
    )

    source_types = {}
    for s in state.all_sources.values():
        source_types[s.source_type] = source_types.get(s.source_type, 0) + 1
    source_summary = ", ".join(f"{v} {k}" for k, v in source_types.items())

    conf = state.__dict__.get("_confidence", 0.6)
    gaps = state.__dict__.get("_knowledge_gaps", [])
    method_notes = state.__dict__.get("_methodological_notes", "")

    messages = [
        SystemMessage(content=REPORT_WRITER_SYSTEM),
        HumanMessage(content=(
            f"Research topic: {state.topic}\n\n"
            f"Research plan overview:\n{state.research_plan[:500]}\n\n"
            f"Key findings:\n{findings_text}\n\n"
            f"Synthesis:\n{state.synthesis_notes[:2000]}\n\n"
            f"Conflicts:\n{conflict_text or 'None detected'}\n\n"
            f"Knowledge gaps:\n" + "\n".join(f"• {g}" for g in gaps) + "\n\n"
            f"Sources: {source_summary}  (total: {len(state.all_sources)})\n"
            f"Iterations: {state.current_iteration}\n"
            f"Methodological notes: {method_notes}\n\n"
            "Write the complete research report."
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

        # Build sections
        def parse_section(d: dict) -> ReportSection:
            subs = [parse_section(s) for s in d.get("subsections", [])]
            return ReportSection(
                title=d.get("title", ""),
                content=d.get("content", ""),
                subsections=subs,
            )

        sections = [parse_section(s) for s in data.get("sections", [])]

        report = ResearchReport(
            title=data.get("title", f"Research Report: {state.topic}"),
            topic=state.topic,
            executive_summary=data.get("executive_summary", ""),
            sections=sections,
            key_findings=state.key_findings,
            conflicts_identified=state.conflicts,
            methodology=data.get("methodology", ""),
            limitations=data.get("limitations", ""),
            sources=list(state.all_sources.values()),
            confidence_score=conf,
            total_sources=len(state.all_sources),
            research_iterations=state.current_iteration,
        )

        state.report = report
        state.status = "complete"

        print_success(
            f"Report written: '{report.title}' — "
            f"{len(sections)} sections, {len(report.sources)} sources"
        )
        for s in sections:
            print_info(f"  § {s.title}")

    except Exception as e:
        logger.error(f"Report writer failed: {e}")
        state.errors.append(f"Report writer error: {e}")
        # Minimal fallback report
        state.report = ResearchReport(
            title=f"Research Report: {state.topic}",
            topic=state.topic,
            executive_summary=state.synthesis_notes or "Research completed.",
            key_findings=state.key_findings,
            sources=list(state.all_sources.values()),
            total_sources=len(state.all_sources),
            research_iterations=state.current_iteration,
        )
        state.status = "complete"

    return state
