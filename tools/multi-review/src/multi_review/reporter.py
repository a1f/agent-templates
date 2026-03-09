"""Markdown and JSON report formatters."""

import json
from dataclasses import asdict
from io import StringIO

from rich.console import Console
from rich.table import Table
from rich.text import Text

from multi_review.constants import SEVERITY_ORDER
from multi_review.types import MergedFinding, OutputFormat, ReviewReport, Severity


def format_report(*, report: ReviewReport, output_format: OutputFormat) -> str:
    """Format a ReviewReport as markdown or JSON."""
    if output_format == OutputFormat.JSON:
        return _format_json(report)
    return _format_markdown(report)


def _format_json(report: ReviewReport) -> str:
    """Serialize report to JSON."""
    data = asdict(report)
    return json.dumps(data, indent=2, default=str)


def _format_markdown(report: ReviewReport) -> str:
    """Render report as markdown."""
    lines: list[str] = []
    lines.append(f"# Multi-Review Report: {report.task.value}")
    lines.append("")

    models_used = sorted({r.model_name for r in report.model_results})
    lines.append(f"**Models**: {', '.join(models_used)}")
    lines.append(f"**Context**: {report.context_type.value}")
    if report.files_reviewed:
        lines.append(f"**Files**: {len(report.files_reviewed)}")
    lines.append(f"**Findings**: {len(report.findings)}")
    lines.append("")

    if not report.findings:
        lines.append("No issues found.")
        return "\n".join(lines)

    grouped: dict[Severity, list[MergedFinding]] = {}
    for finding in report.findings:
        grouped.setdefault(finding.severity, []).append(finding)

    for severity in sorted(
        grouped,
        key=lambda s: SEVERITY_ORDER[s],
        reverse=True,
    ):
        lines.append(f"## {severity.value}")
        lines.append("")
        for finding in grouped[severity]:
            agreement = f"[{', '.join(finding.models)}]"
            lines.append(
                f"- **{finding.file}:{finding.line}** — "
                f"[{finding.category}] {finding.issue} {agreement}"
            )
        lines.append("")

    # Model summary
    lines.append("## Model Summary")
    lines.append("")
    for result in report.model_results:
        status = "ok" if result.success else f"failed: {result.error}"
        lines.append(
            f"- **{result.model_name}**: {len(result.findings)} findings, "
            f"{result.duration_seconds:.1f}s ({status})"
        )
    lines.append("")

    return "\n".join(lines)


def print_report_rich(*, report: ReviewReport) -> None:
    """Print a colored summary table to the terminal."""
    console = Console()

    if not report.findings:
        console.print("[green]No issues found.[/green]")
        return

    table = Table(title=f"Multi-Review: {report.task.value}")
    table.add_column("Sev", style="bold", width=8)
    table.add_column("Location", style="cyan")
    table.add_column("Issue")
    table.add_column("Category", style="dim")
    table.add_column("Models", style="magenta")

    for finding in report.findings:
        sev_text = _severity_styled(finding.severity)
        table.add_row(
            sev_text,
            f"{finding.file}:{finding.line}",
            finding.issue,
            finding.category,
            ", ".join(finding.models),
        )

    console.print(table)

    # Summary line
    total = len(report.findings)
    critical = sum(1 for f in report.findings if f.severity == Severity.CRITICAL)
    major = sum(1 for f in report.findings if f.severity == Severity.MAJOR)
    console.print(
        f"\n[bold]{total}[/bold] findings: "
        f"[red]{critical} critical[/red], "
        f"[yellow]{major} major[/yellow]"
    )


def render_report_to_string(*, report: ReviewReport) -> str:
    """Render rich table to a plain string (for testing/piping)."""
    buf = StringIO()
    console = Console(file=buf, force_terminal=False, width=120)

    if not report.findings:
        console.print("No issues found.")
        return buf.getvalue()

    table = Table(title=f"Multi-Review: {report.task.value}")
    table.add_column("Sev", width=8)
    table.add_column("Location")
    table.add_column("Issue")
    table.add_column("Category")
    table.add_column("Models")

    for finding in report.findings:
        table.add_row(
            finding.severity.value,
            f"{finding.file}:{finding.line}",
            finding.issue,
            finding.category,
            ", ".join(finding.models),
        )

    console.print(table)
    return buf.getvalue()


def _severity_styled(severity: Severity) -> Text:
    """Return a Rich Text with severity-appropriate color."""
    colors: dict[Severity, str] = {
        Severity.CRITICAL: "bold red",
        Severity.MAJOR: "yellow",
        Severity.MINOR: "blue",
        Severity.LOW: "dim",
    }
    return Text(severity.value, style=colors.get(severity, ""))
