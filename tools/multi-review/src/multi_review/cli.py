"""Click CLI entry point for multi-review."""

import asyncio
import sys
from pathlib import Path

import click
import structlog

from multi_review.config import (
    AppConfig,
    check_model_availability,
    generate_default_config,
    load_config,
)
from multi_review.consensus import merge_findings
from multi_review.exceptions import ConfigError, ContextError, MultiReviewError
from multi_review.reporter import format_report, print_report_rich
from multi_review.runner import run_models
from multi_review.types import (
    ContextType,
    OutputFormat,
    ReviewReport,
    TaskType,
)


def _configure_logging(*, verbose: bool) -> None:
    """Set up structlog with appropriate level."""
    import logging

    log_level = logging.DEBUG if verbose else logging.WARNING
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )


@click.group()
def main() -> None:
    """Multi-model code review tool."""


@main.command(name="run")
@click.argument("files", nargs=-1, type=click.Path())
@click.option(
    "-t", "--task",
    type=click.Choice([t.value for t in TaskType], case_sensitive=False),
    default=None,
    help="Review task type.",
)
@click.option("--models", default=None, help="Comma-separated model names to use.")
@click.option("-c", "--config", "config_path", type=click.Path(exists=True), default=None)
@click.option(
    "--context-type",
    type=click.Choice([c.value for c in ContextType], case_sensitive=False),
    default=None,
    help="How to gather code context.",
)
@click.option(
    "-f", "--format", "output_format",
    type=click.Choice([f.value for f in OutputFormat], case_sensitive=False),
    default=None,
    help="Output format.",
)
@click.option("-v", "--verbose", is_flag=True, default=False, help="Verbose logging.")
def run_review(
    files: tuple[str, ...],
    task: str | None,
    models: str | None,
    config_path: str | None,
    context_type: str | None,
    output_format: str | None,
    verbose: bool,
) -> None:
    """Run multi-model code review on files or git diff."""
    _configure_logging(verbose=verbose)

    try:
        cfg = load_config(
            config_path=Path(config_path) if config_path else None,
        )
    except ConfigError as exc:
        click.echo(f"Config error: {exc}", err=True)
        sys.exit(1)

    resolved_task = TaskType(task) if task else cfg.defaults.task
    resolved_context = ContextType(context_type) if context_type else cfg.defaults.context_type
    resolved_format = OutputFormat(output_format) if output_format else cfg.output.format

    # Determine context type from arguments
    if files and resolved_context == ContextType.DIFF:
        first_path = Path(files[0])
        if first_path.is_dir():
            resolved_context = ContextType.DIRECTORY
        else:
            resolved_context = ContextType.FILES

    # Filter models
    available = check_model_availability(config=cfg)
    if models:
        selected_names = {n.strip() for n in models.split(",")}
        available = [m for m in available if m.name in selected_names]

    if not available:
        click.echo("No models available. Install claude, codex, or configure models.", err=True)
        sys.exit(1)

    click.echo(
        f"Running {resolved_task.value} with {len(available)} model(s): "
        f"{', '.join(m.name for m in available)}",
        err=True,
    )

    try:
        report = asyncio.run(
            _run_pipeline(
                models=available,
                task=resolved_task,
                context_type=resolved_context,
                files=list(files),
            )
        )
    except (ContextError, MultiReviewError) as exc:
        click.echo(f"Error: {exc}", err=True)
        sys.exit(1)

    # Output
    if resolved_format == OutputFormat.MARKDOWN and sys.stdout.isatty():
        print_report_rich(report=report)
    else:
        output = format_report(report=report, output_format=resolved_format)
        click.echo(output)


async def _run_pipeline(
    *,
    models: list,  # type: ignore[type-arg]
    task: TaskType,
    context_type: ContextType,
    files: list[str],
) -> ReviewReport:
    """Execute the full review pipeline."""
    results = await run_models(
        models=models,
        task=task,
        context_type=context_type,
        files=files,
    )

    all_findings = []
    for result in results:
        all_findings.extend(result.findings)

    merged = merge_findings(findings=all_findings)

    files_reviewed: tuple[str, ...] = tuple(files) if files else ()

    return ReviewReport(
        task=task,
        findings=tuple(merged),
        model_results=tuple(results),
        context_type=context_type,
        files_reviewed=files_reviewed,
    )


@main.group()
def config() -> None:
    """Configuration management commands."""


@config.command("show")
def config_show() -> None:
    """Show current effective configuration."""
    try:
        cfg = load_config()
    except ConfigError as exc:
        click.echo(f"Config error: {exc}", err=True)
        sys.exit(1)

    click.echo(cfg.model_dump_json(indent=2))


@config.command("init")
def config_init() -> None:
    """Create default configuration file."""
    config_dir = Path.home() / ".config" / "multi-review"
    config_dir.mkdir(parents=True, exist_ok=True)
    config_file = config_dir / "config.yaml"

    if config_file.exists():
        click.echo(f"Config already exists: {config_file}", err=True)
        sys.exit(1)

    config_file.write_text(generate_default_config(), encoding="utf-8")
    click.echo(f"Created config: {config_file}")
