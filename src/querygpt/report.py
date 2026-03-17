"""Rich console reporting for QueryGPT."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from querygpt.models import Query, Schema
from querygpt.schema.validator import ValidationResult
from querygpt.translator.optimizer import OptimizationReport

console = Console()


def print_query(query: Query) -> None:
    """Display a generated SQL query."""
    # SQL with syntax highlighting
    console.print(Panel(
        Syntax(query.sql, "sql", theme="monokai", line_numbers=False),
        title="Generated SQL",
        border_style="green" if query.confidence > 0.5 else "yellow",
    ))

    # Metadata
    meta = Table(show_header=False, box=None, padding=(0, 2))
    meta.add_column("Key", style="dim")
    meta.add_column("Value")
    meta.add_row("Confidence", f"{query.confidence:.0%}")
    meta.add_row("Tables", ", ".join(query.tables_used) or "none")
    if query.warnings:
        meta.add_row("Warnings", "; ".join(query.warnings))
    console.print(meta)


def print_schema(schema: Schema) -> None:
    """Display schema metadata."""
    console.print(Panel(f"Schema: [bold]{schema.name}[/bold]", border_style="blue"))

    for table in schema.tables:
        t = Table(title=f"{table.name}", show_header=True)
        t.add_column("Column", style="cyan")
        t.add_column("Type", style="green")
        t.add_column("PK", style="yellow")
        t.add_column("FK", style="magenta")
        t.add_column("Nullable", style="dim")

        for col in table.columns:
            t.add_row(
                col.name,
                col.data_type.value,
                "PK" if col.primary_key else "",
                col.foreign_key or "",
                "Yes" if col.nullable else "No",
            )
        console.print(t)
        console.print()


def print_validation(result: ValidationResult) -> None:
    """Display validation results."""
    style = "green" if result.valid else "red"
    console.print(Panel(result.summary, title="Validation", border_style=style))

    for issue in result.issues:
        icon = "[red]ERROR[/red]" if issue.level == "error" else "[yellow]WARN[/yellow]"
        console.print(f"  {icon}: {issue.message}")
        if issue.suggestion:
            console.print(f"         [dim]{issue.suggestion}[/dim]")


def print_optimization(report: OptimizationReport) -> None:
    """Display optimization suggestions."""
    console.print(Panel(
        f"Estimated cost: [bold]{report.estimated_cost}[/bold] | {report.summary}",
        title="Optimization Analysis",
        border_style="blue",
    ))

    for s in report.suggestions:
        color = {"info": "cyan", "warning": "yellow", "critical": "red"}.get(s.severity, "white")
        console.print(f"  [{color}]{s.severity.upper()}[/{color}] [{s.category}] {s.message}")

    if report.index_recommendations:
        console.print("\n[bold]Recommended indexes:[/bold]")
        for idx in report.index_recommendations:
            console.print(Syntax(idx, "sql", theme="monokai", line_numbers=False))
