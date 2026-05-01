"""
Report formatters.

Converts a ResearchReport into:
  • A rich Markdown document
  • A plain JSON dump
"""
from __future__ import annotations

import json
from datetime import datetime
from schemas import ResearchReport, ReportSection


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _render_section(section: ReportSection, level: int = 2) -> str:
    hashes = "#" * level
    lines = [f"{hashes} {section.title}", "", section.content]
    for sub in section.subsections:
        lines.append("")
        lines.append(_render_section(sub, level + 1))
    return "\n".join(lines)


def to_markdown(report: ResearchReport) -> str:
    lines = [
        f"# {report.title}",
        "",
        f"> **Generated:** {report.generated_at[:19].replace('T', ' ')} UTC  ",
        f"> **Topic:** {report.topic}  ",
        f"> **Sources:** {report.total_sources}  ",
        f"> **Research Iterations:** {report.research_iterations}  ",
        f"> **Confidence Score:** {report.confidence_score:.0%}",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        report.executive_summary,
        "",
        "---",
        "",
        "## Key Findings",
        "",
    ]

    for i, finding in enumerate(report.key_findings, 1):
        lines.append(f"{i}. {finding}")

    lines += ["", "---", ""]

    for section in report.sections:
        lines.append(_render_section(section, level=2))
        lines.append("")
        lines.append("---")
        lines.append("")

    # Conflicts
    if report.conflicts_identified:
        lines += [
            "## Conflicting Evidence",
            "",
            "The following contradictions were identified across sources:",
            "",
        ]
        for c in report.conflicts_identified:
            status = "✅ Resolved" if c.resolved else "⚠️ Unresolved"
            lines += [
                f"### {c.topic}",
                f"**Status:** {status}",
                "",
                f"**Position A:** {c.claim_a}",
                "",
                f"**Position B:** {c.claim_b}",
                "",
            ]
            if c.resolution:
                lines += [f"**Resolution:** {c.resolution}", ""]
        lines += ["---", ""]

    # Methodology & limitations
    if report.methodology:
        lines += ["## Methodology", "", report.methodology, "", "---", ""]

    if report.limitations:
        lines += ["## Limitations & Caveats", "", report.limitations, "", "---", ""]

    # Sources
    lines += ["## Sources", ""]
    for i, s in enumerate(report.sources, 1):
        src_type = f"[{s.source_type}]"
        url_part = f" — {s.url}" if s.url else ""
        cred = f"credibility: {s.credibility_score:.2f}"
        lines.append(f"{i}. **{s.title or 'Untitled'}** {src_type}{url_part} _{cred}_")

    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def to_json(report: ResearchReport, indent: int = 2) -> str:
    return report.model_dump_json(indent=indent)


# ---------------------------------------------------------------------------
# Save helpers
# ---------------------------------------------------------------------------

def save_report(report: ResearchReport, output_dir: str = "output") -> dict[str, str]:
    """Save report as both Markdown and JSON. Returns paths."""
    import os, re
    os.makedirs(output_dir, exist_ok=True)

    slug = re.sub(r"[^\w]+", "_", report.topic.lower())[:40]
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    base = f"{output_dir}/research_{slug}_{ts}"

    md_path = base + ".md"
    json_path = base + ".json"

    with open(md_path, "w", encoding="utf-8") as f:
        f.write(to_markdown(report))

    with open(json_path, "w", encoding="utf-8") as f:
        f.write(to_json(report))

    return {"markdown": md_path, "json": json_path}
