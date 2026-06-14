"""Pretty-printing helpers so notebooks read like a report, not a debugger.

Rich is used because:
- It renders nicely in both Jupyter and plain terminals
- Tables for retrieval results are far more readable than DataFrame dumps
- One library replaces five hand-rolled formatting helpers
"""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

_console = Console()


def md(text: str) -> None:
    """Render markdown — good for displaying LLM responses."""
    _console.print(Markdown(text))


def panel(text: str, title: str = "", style: str = "cyan") -> None:
    _console.print(Panel(text, title=title, border_style=style))


def results_table(rows: list[dict[str, Any]], title: str = "Results") -> None:
    """Render a list-of-dicts as a table. Auto-discovers columns."""
    if not rows:
        _console.print(f"[yellow]{title}: (no rows)[/yellow]")
        return
    table = Table(title=title, show_lines=True)
    columns = list(rows[0].keys())
    for c in columns:
        table.add_column(str(c))
    for row in rows:
        table.add_row(*[str(row.get(c, "")) for c in columns])
    _console.print(table)


def compare_side_by_side(left: str, right: str, left_title: str = "Left", right_title: str = "Right") -> None:
    """Two-column comparison panel — perfect for Gen 1 vs Gen 2 answers."""
    table = Table.grid(expand=True)
    table.add_column(ratio=1)
    table.add_column(ratio=1)
    table.add_row(
        Panel(left, title=left_title, border_style="blue"),
        Panel(right, title=right_title, border_style="green"),
    )
    _console.print(table)
