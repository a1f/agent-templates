"""The imperative shell: real git subprocesses, JSON on stdout, verdict as exit code.

Exit codes are the verdict — 0 pass, 1 review (a judge must rule), 2 block, 3 the gate
could not measure — so an unmeasured change never reads as a passing one. A launch or
usage failure exits 1 or 2 as well, which is why the JSON `verdict`, not the exit code,
is what a caller routes on.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from dataclasses import asdict
from typing import Any

import click

from .constants import (
    EXIT_ERROR,
    GIT_DIFF_FLAGS,
    INLINE_TEST_SUFFIXES,
    REPORT_ROLE,
    SCHEMA_VERSION,
)
from .policy import measure
from .sizing import added_line_numbers
from .types import CommandRunner, SizeError, SizeReport


def _subprocess_runner(*, argv: tuple[str, ...]) -> str:
    """The real boundary: run a command, returning stdout, SizeError on failure."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        argv, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        detail: str = result.stderr.strip() or result.stdout.strip()
        raise SizeError(f"{shlex.join(argv)} failed: {detail}")
    return result.stdout


def report_for(*, base: str, head: str, repo: str, run: CommandRunner) -> SizeReport:
    """Measure what `base...head` adds in `repo`.

    Two questions for git: the diff, then the post-image of each file whose tests can
    live inside it — the only way a `#[cfg(test)]` block can be told from code.
    """
    diff_text: str = run(argv=("git", "-C", repo, *GIT_DIFF_FLAGS, f"{base}...{head}"))
    return measure(
        diff_text=diff_text,
        sources={
            path: run(argv=("git", "-C", repo, "show", f"{head}:{path}"))
            for path in added_line_numbers(diff_text=diff_text)
            if path.endswith(tuple(INLINE_TEST_SUFFIXES))
        },
    )


def summarize(*, report: SizeReport) -> str:
    """One line to act on: the counts, the caps, and the call."""
    return (
        f"{report.verdict}: code {report.code.lines} added lines across "
        f"{report.code.files} file(s) (target {report.code.target}, cap "
        f"{report.code.limit}, band {report.code.band}); prose {report.prose.lines} "
        f"(target {report.prose.target}, cap {report.prose.limit}); "
        f"{report.tests.lines} test and {report.generated.lines} generated lines "
        f"excluded"
    )


def run_cli(
    *, base: str, head: str, repo: str, run: CommandRunner | None = None
) -> int:
    """Measure `base...head` in `repo`, print the report, return the verdict's code."""
    try:
        report: SizeReport = report_for(
            base=base,
            head=head,
            repo=repo,
            run=run if run is not None else _subprocess_runner,
        )
    except (SizeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "role": REPORT_ROLE,
        "base": base,
        "head": head,
        **asdict(report),
        "summary": summarize(report=report),
    }
    print(json.dumps(payload, indent=2))
    return report.verdict.severity


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--base", required=True, metavar="REF", help="Ref the PR branches from.")
@click.option("--head", default="HEAD", show_default=True, help="Ref being measured.")
@click.option("--repo", default=".", show_default=True, help="Repository to measure.")
def cli(*, base: str, head: str, repo: str) -> None:
    """Judge a change's size: which lines count, and whether that many may proceed."""
    raise SystemExit(run_cli(base=base, head=head, repo=repo))
