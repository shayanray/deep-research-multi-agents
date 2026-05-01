"""
Pretty-printing utilities using Rich.
"""
from __future__ import annotations

import sys
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text
from rich import box

console = Console(stderr=False)
err_console = Console(stderr=True)


# ---------------------------------------------------------------------------
# Status helpers
# ---------------------------------------------------------------------------

STATUS_ICONS = {
    "planning":    "🗺️ ",
    "researching": "🔍",
    "analyzing":   "🧠",
    "synthesizing":"🔗",
    "writing":     "✍️ ",
    "complete":    "✅",
    "error":       "❌",
}


def print_header(title: str):
    console.print(Panel(
        f"[bold cyan]{title}[/bold cyan]",
        border_style="bright_blue",
        expand=False,
        padding=(1, 4),
    ))


def print_phase(phase: str, message: str = ""):
    icon = STATUS_ICONS.get(phase, "▶")
    console.print(f"\n{icon}  [bold yellow]{phase.upper()}[/bold yellow]  {message}")
    console.print("─" * 60, style="dim")


def print_info(message: str):
    console.print(f"  [cyan]→[/cyan] {message}")


def print_success(message: str):
    console.print(f"  [green]✓[/green] {message}")


def print_warning(message: str):
    console.print(f"  [yellow]⚠[/yellow]  {message}")


def print_error(message: str):
    err_console.print(f"  [red]✗[/red] {message}")


def print_source_table(sources, max_rows: int = 10):
    if not sources:
        return
    table = Table(title="Sources Retrieved", box=box.SIMPLE_HEAVY,
                  show_lines=False, border_style="dim")
    table.add_column("ID", style="dim", width=8)
    table.add_column("Type", style="cyan", width=10)
    table.add_column("Title", style="white", max_width=50)
    table.add_column("Cred.", style="green", justify="right", width=6)

    for s in list(sources)[:max_rows]:
        cred = f"{s.credibility_score:.2f}"
        table.add_row(s.id, s.source_type, s.title[:50], cred)

    console.print(table)


def print_conflicts(conflicts):
    if not conflicts:
        return
    console.print("\n[bold red]⚡ Conflicts Detected[/bold red]")
    for c in conflicts:
        status = "[green]resolved[/green]" if c.resolved else "[red]unresolved[/red]"
        console.print(f"  • {c.topic}  [{status}]")
        console.print(f"    A: {c.claim_a[:80]}", style="dim")
        console.print(f"    B: {c.claim_b[:80]}", style="dim")
        if c.resolution:
            console.print(f"    → {c.resolution[:100]}", style="italic cyan")


def make_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console,
    )
