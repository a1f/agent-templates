"""The imperative shell: real git subprocesses, JSON on stdout, verdict as exit code.

Exit codes are the verdict: 0 pass, 1 review (a judge must rule), 2 block, 3 the gate
could not measure (bad ref, not a repository). A usage error from click also exits
non-zero, so a broken invocation can never read as a pass.
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from dataclasses import asdict
from typing import Any

import click

from .constants import EXIT_CODES, EXIT_ERROR, GIT_DIFF_FLAGS, INLINE_TEST_SUFFIXES
from .sizing import changed_paths, measure
from .types import CommandRunner, SizeError, SizeReport, Verdict


def _subprocess_runner(*, argv: tuple[str, ...]) -> str:
    """The real boundary: run a command, returning stdout, SizeError on failure."""
    result: subprocess.CompletedProcess[str] = subprocess.run(
        argv, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        detail: str = result.stderr.strip() or result.stdout.strip()
        raise SizeError(f"{shlex.join(argv)} failed: {detail}")
    return result.stdout


def diff_text(*, run: CommandRunner, repo: str, base: str, head: str) -> str:
    """The diff the PR would show: every line added on this branch since `base`."""
    return run(argv=("git", "-C", repo, *GIT_DIFF_FLAGS, f"{base}...{head}"))


def inline_test_sources(
    *, run: CommandRunner, repo: str, head: str, paths: tuple[str, ...]
) -> dict[str, str]:
    """Post-image content of the changed files whose tests could live inside them."""
    wanted: tuple[str, ...] = tuple(
        path for path in paths if path.endswith(tuple(INLINE_TEST_SUFFIXES))
    )
    return {
        path: run(argv=("git", "-C", repo, "show", f"{head}:{path}")) for path in wanted
    }


def summarize(*, report: SizeReport) -> str:
    """One line a human or a judge can act on: the counts, the caps, the call."""
    return (
        f"{report.verdict}: code {report.code.lines} added lines across "
        f"{report.code.files} file(s) (target {report.code.target}, cap "
        f"{report.code.limit}, band {report.code.band}); prose {report.prose.lines} "
        f"(target {report.prose.target}, cap {report.prose.limit}); "
        f"{report.tests.lines} test and {report.generated.lines} generated lines "
        f"excluded"
    )


def run_cli(
    *,
    base: str,
    head: str,
    repo: str,
    run: CommandRunner | None = None,
) -> int:
    """Measure `base...head` in `repo`, print the report, return the verdict's code."""
    runner: CommandRunner = run if run is not None else _subprocess_runner
    try:
        text: str = diff_text(run=runner, repo=repo, base=base, head=head)
        report: SizeReport = measure(
            diff_text=text,
            sources=inline_test_sources(
                run=runner, repo=repo, head=head, paths=changed_paths(diff_text=text)
            ),
        )
    except (SizeError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ERROR
    payload: dict[str, Any] = {
        "schema_version": "v1",
        "base": base,
        "head": head,
        **asdict(report),
        "summary": summarize(report=report),
    }
    print(json.dumps(payload, indent=2))
    return EXIT_CODES[Verdict(report.verdict)]


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("--base", required=True, metavar="REF", help="Ref the PR branches from.")
@click.option("--head", default="HEAD", show_default=True, help="Ref being measured.")
@click.option("--repo", default=".", show_default=True, help="Repository to measure.")
def cli(*, base: str, head: str, repo: str) -> None:
    """Judge a PR's size: which lines count, and whether that many may proceed."""
    raise SystemExit(run_cli(base=base, head=head, repo=repo))
