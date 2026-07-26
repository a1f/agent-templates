"""Tests for the PR size gate (a unified diff -> what it costs, by budget class).

The tool is a functional core (parse the diff, classify each path, apply the bands)
behind a thin imperative shell (git subprocess). We test the core on literal diff text
and the shell through an injected fake runner — never a real git.
"""

from __future__ import annotations

from typing import Final

import pytest

from pr_size.policy import code_budget
from pr_size.sizing import added_line_numbers, changed_files, classify
from pr_size.types import ChangedFile, FileKind


def _diff(*, path: str, added: int, start: int = 1) -> str:
    """A minimal unified diff adding `added` lines to `path` at `start`."""
    body: str = "".join(f"+line {index}\n" for index in range(added))
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        f"@@ -0,0 +{start},{added} @@\n"
        f"{body}"
    )


SMALL_CHANGE: Final[int] = 10


def test_added_lines_are_numbered_from_their_hunk_header() -> None:
    diff_text: str = _diff(path="cart.py", added=3, start=40)

    assert added_line_numbers(diff_text=diff_text) == {"cart.py": (40, 41, 42)}


def test_every_changed_path_is_reported_even_when_it_only_lost_lines() -> None:
    deletion: str = (
        "diff --git a/gone.py b/gone.py\n"
        "--- a/gone.py\n"
        "+++ b/gone.py\n"
        "@@ -1,3 +0,0 @@\n"
        "-one\n-two\n-three\n"
    )

    numbered: dict[str, tuple[int, ...]] = added_line_numbers(
        diff_text=deletion + _diff(path="cart.py", added=SMALL_CHANGE)
    )

    assert numbered["gone.py"] == ()
    assert len(numbered["cart.py"]) == SMALL_CHANGE


BIG_CHANGE: Final[int] = 40


def _kind_lines(*, diff_text: str, kind: FileKind) -> int:
    return sum(
        file.lines for file in changed_files(diff_text=diff_text) if file.kind is kind
    )


def test_a_code_file_is_reported_with_the_lines_it_gained() -> None:
    files = changed_files(diff_text=_diff(path="cart.py", added=SMALL_CHANGE))

    assert files == (
        ChangedFile(
            path="cart.py", kind=FileKind.CODE, lines=SMALL_CHANGE, test_lines=0
        ),
    )


def test_tests_prose_and_generated_files_classify_apart_from_code() -> None:
    diff_text: str = (
        _diff(path="cart.py", added=SMALL_CHANGE)
        + _diff(path="tests/test_cart.py", added=BIG_CHANGE)
        + _diff(path="web/cart.test.ts", added=BIG_CHANGE)
        + _diff(path="docs/guide.md", added=BIG_CHANGE)
        + _diff(path="uv.lock", added=BIG_CHANGE)
        + _diff(path="web/dist/bundle.js", added=BIG_CHANGE)
    )

    assert _kind_lines(diff_text=diff_text, kind=FileKind.CODE) == SMALL_CHANGE
    assert _kind_lines(diff_text=diff_text, kind=FileKind.TEST) == BIG_CHANGE * 2
    assert _kind_lines(diff_text=diff_text, kind=FileKind.PROSE) == BIG_CHANGE
    assert _kind_lines(diff_text=diff_text, kind=FileKind.GENERATED) == BIG_CHANGE * 2


def test_a_lockfile_under_tests_is_generated_not_a_test() -> None:
    assert classify(path="tests/fixtures/uv.lock") is FileKind.GENERATED
    assert classify(path="tests/fixtures/data.md") is FileKind.TEST


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
        assert_eq!(format!("{}", "{"), "{");
    }
}
"""
RUST_CODE_LINES: Final[int] = 4


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


def test_a_rust_cfg_test_block_is_charged_to_tests_not_to_code() -> None:
    path: Final[str] = "src/cart.rs"

    files = changed_files(
        diff_text=_whole_file_diff(path=path, content=RUST_WITH_INLINE_TESTS),
        sources={path: RUST_WITH_INLINE_TESTS},
    )

    assert files[0].lines == RUST_CODE_LINES
    assert files[0].test_lines == (
        len(RUST_WITH_INLINE_TESTS.splitlines()) - RUST_CODE_LINES
    )


def test_a_declared_test_module_does_not_swallow_the_code_below_it() -> None:
    path: Final[str] = "src/lib.rs"
    source: Final[str] = (
        "#[cfg(test)]\nmod tests;\n\npub fn total() -> u32 {\n    3\n}\n"
    )

    files = changed_files(
        diff_text=_whole_file_diff(path=path, content=source), sources={path: source}
    )

    assert files[0].test_lines == 2
    assert files[0].lines == 4


@pytest.mark.parametrize(
    ("files", "lines", "verdict", "band"),
    [
        (1, 35, "pass", "target"),
        (5, 35, "pass", "target"),
        (3, 36, "review", "many-files"),
        (3, 50, "review", "many-files"),
        (3, 51, "block", "over-limit"),
        (9, 400, "block", "over-limit"),
        (1, 36, "review", "cohesion"),
        (2, 75, "review", "cohesion"),
        (2, 76, "review", "cohesion-strict"),
        (2, 100, "review", "cohesion-strict"),
        (2, 101, "block", "over-limit"),
    ],
)
def test_code_bands(files: int, lines: int, verdict: str, band: str) -> None:
    budget = code_budget(files=files, lines=lines)

    assert budget.verdict == verdict
    assert budget.band == band
