"""Tests for the PR size gate (a unified diff -> what it costs, by budget class).

The tool is a functional core (parse the diff, classify each path, apply the bands)
behind a thin imperative shell (git subprocess). We test the core on literal diff text
and the shell through an injected fake runner — never a real git.
"""

from __future__ import annotations

from typing import Final

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
