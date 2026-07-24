"""Tests for the PR size gate (a unified diff -> a countable-lines verdict).

The tool is a functional core (classify each changed path, count the added lines that
count, apply the bands) behind a thin imperative shell (git subprocess). We test the
core through `measure` on literal diff text and the shell through an injected fake
runner — never a real git.
"""

from __future__ import annotations

import json
from typing import Final

import pytest

from pr_size import SizeError, measure
from pr_size.cli import run_cli


def _diff(*, path: str, added: int, start: int = 1) -> str:
    """A minimal unified diff adding `added` lines to `path`."""
    body: str = "".join(f"+line {index}\n" for index in range(added))
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +{start},{added} @@\n"
        f"{body}"
    )


def _whole_file_diff(*, path: str, content: str) -> str:
    """A unified diff that adds `content` as a new file, so line numbers line up."""
    lines: list[str] = content.splitlines()
    body: str = "".join(f"+{line}\n" for line in lines)
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- /dev/null\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}"
    )


SMALL_CHANGE: Final[int] = 10
BIG_CHANGE: Final[int] = 40

RUST_WITH_INLINE_TESTS: Final[str] = """\
pub fn total(items: &[u32]) -> u32 {
    items.iter().sum()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn sums_items() {
        assert_eq!(total(&[1, 2]), 3);
    }
}
"""
RUST_CODE_LINES: Final[int] = 4


def test_counts_added_lines_of_one_code_file() -> None:
    report = measure(diff_text=_diff(path="cart.py", added=SMALL_CHANGE))

    assert report.code.lines == SMALL_CHANGE
    assert report.code.files == 1
    assert report.verdict == "pass"


def test_test_files_are_never_charged_to_the_code_budget() -> None:
    report = measure(
        diff_text=_diff(path="cart.py", added=SMALL_CHANGE)
        + _diff(path="tests/test_cart.py", added=BIG_CHANGE)
        + _diff(path="web/cart.test.ts", added=BIG_CHANGE)
    )

    assert report.code.lines == SMALL_CHANGE
    assert report.code.files == 1
    assert report.tests.lines == BIG_CHANGE * 2
    assert report.verdict == "pass"


def test_prose_and_generated_files_stay_out_of_the_code_budget() -> None:
    report = measure(
        diff_text=_diff(path="cart.py", added=SMALL_CHANGE)
        + _diff(path="docs/guide.md", added=BIG_CHANGE)
        + _diff(path="uv.lock", added=BIG_CHANGE)
        + _diff(path="web/dist/bundle.js", added=BIG_CHANGE)
    )

    assert report.code.lines == SMALL_CHANGE
    assert report.code.files == 1
    assert report.prose.lines == BIG_CHANGE
    assert report.prose.files == 1
    assert report.generated.lines == BIG_CHANGE * 2


def test_rust_cfg_test_block_is_charged_to_tests_not_code() -> None:
    path: Final[str] = "src/cart.rs"

    report = measure(
        diff_text=_whole_file_diff(path=path, content=RUST_WITH_INLINE_TESTS),
        sources={path: RUST_WITH_INLINE_TESTS},
    )

    assert report.code.lines == RUST_CODE_LINES
    assert (
        report.tests.lines == len(RUST_WITH_INLINE_TESTS.splitlines()) - RUST_CODE_LINES
    )


def _spread(*, files: int, lines: int) -> str:
    """A diff over `files` code files carrying `lines` added lines between them."""
    each: list[int] = [1] * files
    each[0] += lines - files
    return "".join(
        _diff(path=f"src/module{index}.py", added=added)
        for index, added in enumerate(each)
    )


@pytest.mark.parametrize(
    ("files", "lines", "verdict"),
    [
        (1, 35, "pass"),
        (5, 35, "pass"),
        (3, 36, "review"),
        (3, 50, "review"),
        (3, 51, "block"),
        (9, 51, "block"),
        (1, 36, "review"),
        (2, 100, "review"),
        (2, 101, "block"),
        (1, 400, "block"),
    ],
)
def test_code_bands(files: int, lines: int, verdict: str) -> None:
    report = measure(diff_text=_spread(files=files, lines=lines))

    assert report.code.lines == lines
    assert report.code.files == files
    assert report.verdict == verdict
    assert report.code.verdict == verdict


@pytest.mark.parametrize(
    ("lines", "verdict"),
    [(100, "pass"), (101, "review"), (150, "review"), (151, "block")],
)
def test_prose_bands(lines: int, verdict: str) -> None:
    report = measure(diff_text=_diff(path="skills/thing/SKILL.md", added=lines))

    assert report.prose.lines == lines
    assert report.prose.verdict == verdict
    assert report.code.verdict == "pass"
    assert report.verdict == verdict


def test_a_pr_is_only_as_good_as_its_worst_budget() -> None:
    report = measure(
        diff_text=_diff(path="cart.py", added=SMALL_CHANGE)
        + _diff(path="README.md", added=200)
    )

    assert report.code.verdict == "pass"
    assert report.verdict == "block"


class FakeGit:
    """Answers the two git questions the shell asks, and records every argv."""

    def __init__(self, *, diff: str, sources: dict[str, str] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self._diff = diff
        self._sources = sources or {}

    def __call__(self, *, argv: tuple[str, ...]) -> str:
        self.calls.append(argv)
        if "diff" in argv:
            return self._diff
        if "show" in argv:
            return self._sources[argv[-1].split(":", 1)[1]]
        return ""


def test_cli_prints_the_report_and_exits_on_the_verdict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    git = FakeGit(diff=_spread(files=4, lines=60))

    exit_code: int = run_cli(base="origin/main", head="HEAD", repo=".", run=git)

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["verdict"] == "block"
    assert payload["code"] == {
        "files": 4,
        "lines": 60,
        "target": 35,
        "limit": 50,
        "band": "over-limit",
        "verdict": "block",
    }
    assert payload["summary"]


def test_cli_reads_rust_post_images_so_inline_tests_are_excluded() -> None:
    path: Final[str] = "src/cart.rs"
    git = FakeGit(
        diff=_whole_file_diff(path=path, content=RUST_WITH_INLINE_TESTS),
        sources={path: RUST_WITH_INLINE_TESTS},
    )

    exit_code: int = run_cli(base="main", head="HEAD", repo="/repo", run=git)

    assert exit_code == 0
    assert ("git", "-C", "/repo", "show", f"HEAD:{path}") in git.calls


def test_cli_exits_non_zero_without_a_verdict_when_git_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def explode(*, argv: tuple[str, ...]) -> str:
        raise SizeError(f"bad revision: {argv[-1]}")

    exit_code: int = run_cli(base="nope", head="HEAD", repo=".", run=explode)

    assert exit_code not in {0, 1, 2}
    assert capsys.readouterr().out == ""


def test_a_declared_test_module_does_not_swallow_the_code_below_it() -> None:
    path: Final[str] = "src/lib.rs"
    source: Final[str] = (
        "#[cfg(test)]\nmod tests;\n\npub fn total() -> u32 {\n    3\n}\n"
    )

    report = measure(
        diff_text=_whole_file_diff(path=path, content=source), sources={path: source}
    )

    assert report.tests.lines == 2
    assert report.code.lines == 4
