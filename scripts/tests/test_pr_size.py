"""Tests for the PR size gate (a unified diff -> what it costs, by budget class).

The tool is a functional core (parse the diff, classify each path, apply the bands)
behind a thin imperative shell (git subprocess). We test the core on literal diff text
and the shell through an injected fake runner — never a real git.
"""

from __future__ import annotations

from typing import Final

from pr_size.sizing import added_line_numbers


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


def test_a_deleted_file_adds_no_phantom_line_to_the_file_before_it() -> None:
    """git writes `+++ /dev/null` for a deletion; it is a header, not an addition."""
    diff_text: str = _diff(path="aaa.py", added=1) + (
        "diff --git a/zzz.py b/zzz.py\n"
        "deleted file mode 100644\n"
        "--- a/zzz.py\n"
        "+++ /dev/null\n"
        "@@ -1,3 +0,0 @@\n"
        "-one\n-two\n-three\n"
    )

    assert added_line_numbers(diff_text=diff_text) == {"aaa.py": (1,)}
