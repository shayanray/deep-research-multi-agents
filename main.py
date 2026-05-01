#!/usr/bin/env python3
"""
Deep Research Agent System
==========================
Usage:
    python main.py "your research topic"
    python main.py "your research topic" --depth 3 --sources 5
    python main.py --interactive

Environment variables (set in .env):
    NVIDIA_API_KEY      — Llama 3.1 70B (preferred)
    ANTHROPIC_API_KEY   — Claude (fallback)
    OPENAI_API_KEY      — GPT-4o (fallback)
"""
from __future__ import annotations

import sys
import os
import argparse
import logging
import time

import warnings
warnings.filterwarnings("ignore")


# Add project root to Python path
sys.path.insert(0, os.path.dirname(__file__))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv()

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich import box

from schemas import ResearchState
from pipeline import get_compiled_graph
from report_formatter import save_report, to_markdown
from logger import (
    print_header, print_phase, print_info,
    print_success, print_error, print_warning, console
)

logging.basicConfig(
    level=logging.WARNING,
    format="%(levelname)s %(name)s: %(message)s",
)


# ---------------------------------------------------------------------------
# Core runner
# ---------------------------------------------------------------------------

def run_research(
    topic: str,
    depth: int = 2,
    max_sources: int = 5,
    output_dir: str = "output",
) -> ResearchState:
    """Run the full deep research pipeline."""

    print_header("🔬 Deep Research Agent System")
    print_info(f"Topic: {topic}")
    print_info(f"Depth: {depth}  |  Max sources/query: {max_sources}")
    console.print()

    # Build initial state
    initial_state = ResearchState(
        topic=topic,
        research_depth=depth,
        max_sources_per_query=max_sources,
    )

    # Compile and run graph
    app = get_compiled_graph()
    start_time = time.time()

    try:
        final_dict = app.invoke(initial_state.model_dump())
        final_state = ResearchState(**final_dict)
    except Exception as e:
        print_error(f"Pipeline error: {e}")
        raise

    elapsed = time.time() - start_time
    console.print(f"\n⏱  Completed in {elapsed:.1f}s", style="dim")

    # Save outputs
    if final_state.report:
        paths = save_report(final_state.report, output_dir)
        console.print()
        console.print(Panel(
            f"[bold green]✅ Research Complete![/bold green]\n\n"
            f"📄 Markdown: [cyan]{paths['markdown']}[/cyan]\n"
            f"📦 JSON:     [cyan]{paths['json']}[/cyan]\n\n"
            f"Sources:    {final_state.report.total_sources}\n"
            f"Findings:   {len(final_state.report.key_findings)}\n"
            f"Conflicts:  {len(final_state.report.conflicts_identified)}\n"
            f"Confidence: {final_state.report.confidence_score:.0%}",
            border_style="green",
            expand=False,
        ))

        # Print markdown preview
        console.print("\n[bold]── Report Preview ──[/bold]\n", style="dim")
        md = to_markdown(final_state.report)
        preview_lines = md.split("\n")[:60]
        console.print("\n".join(preview_lines))
        if len(md.split("\n")) > 60:
            console.print("… (see full report in output files)", style="dim")

    if final_state.errors:
        console.print(f"\n[yellow]⚠  {len(final_state.errors)} non-fatal errors logged.[/yellow]")
        for err in final_state.errors[:5]:
            print_warning(err)

    return final_state


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def interactive_mode():
    console.print(Panel(
        "[bold cyan]Deep Research Agent — Interactive Mode[/bold cyan]\n"
        "Ask a research question and get a structured report.",
        border_style="blue",
    ))

    topic = Prompt.ask("\n🔎 Research topic")
    depth = IntPrompt.ask("Research depth (1=quick, 2=standard, 3=deep, 4=exhaustive)", default=2)
    sources = IntPrompt.ask("Max sources per query", default=5)

    run_research(topic, depth=depth, max_sources=sources)


def main():
    parser = argparse.ArgumentParser(
        description="Deep Research Agent System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("topic", nargs="?", help="Research topic")
    parser.add_argument("--depth", "-d", type=int, default=2,
                        help="Research depth 1-4 (default: 2)")
    parser.add_argument("--sources", "-s", type=int, default=5,
                        help="Max sources per query (default: 5)")
    parser.add_argument("--output", "-o", default="output",
                        help="Output directory (default: output)")
    parser.add_argument("--interactive", "-i", action="store_true",
                        help="Interactive mode")

    args = parser.parse_args()

    if args.interactive or not args.topic:
        interactive_mode()
    else:
        run_research(
            args.topic,
            depth=args.depth,
            max_sources=args.sources,
            output_dir=args.output,
        )


if __name__ == "__main__":
    main()
