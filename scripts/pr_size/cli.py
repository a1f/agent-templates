"""The imperative shell: the real git subprocesses the measurement needs."""

from __future__ import annotations

import shlex
import subprocess

from .constants import GIT_DIFF_FLAGS, INLINE_TEST_SUFFIXES
from .policy import measure
from .sizing import added_line_numbers
from .types import CommandRunner, SizeError, SizeReport


def subprocess_runner(*, argv: tuple[str, ...]) -> str:
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
