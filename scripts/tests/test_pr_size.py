"""Tests for the PR size gate (a unified diff -> what it costs, by budget class).

The tool is a functional core (parse the diff, classify each path, apply the bands)
behind a thin imperative shell (git subprocess). We test the core on literal diff text
and the shell through an injected fake runner; only what git's own encoding decides —
which bytes reach us, in which spelling — is worth a real repository.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Final

import pytest
from click.testing import CliRunner, Result

from pr_size import (
    Budget,
    ChangedFile,
    FileKind,
    SizeError,
    SizeReport,
    added_line_numbers,
    changed_files,
    measure,
)
from pr_size.cli import cli, report_for, run_cli
from pr_size.policy import code_budget
from pr_size.sizing import classify
from validate_return import errors_against

SCHEMAS: Final[Path] = Path(__file__).resolve().parents[2] / "schemas"

# The -c flags keep a test commit independent of any global git config.
_COMMIT: Final[list[str]] = [
    "git",
    "-c",
    "user.email=t@t",
    "-c",
    "user.name=t",
    "commit",
    "-q",
]


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
    files: tuple[ChangedFile, ...] = changed_files(
        diff_text=_diff(path="cart.py", added=SMALL_CHANGE)
    )

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
    path: str = "src/cart.rs"

    files: tuple[ChangedFile, ...] = changed_files(
        diff_text=_whole_file_diff(path=path, content=RUST_WITH_INLINE_TESTS),
        sources={path: RUST_WITH_INLINE_TESTS},
    )

    assert files[0].lines == RUST_CODE_LINES
    assert files[0].test_lines == (
        len(RUST_WITH_INLINE_TESTS.splitlines()) - RUST_CODE_LINES
    )


def test_a_declared_test_module_does_not_swallow_the_code_below_it() -> None:
    path: str = "src/lib.rs"
    source: str = "#[cfg(test)]\nmod tests;\n\npub fn total() -> u32 {\n    3\n}\n"

    files: tuple[ChangedFile, ...] = changed_files(
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
        (3, 51, "block", "over-cap"),
        (9, 400, "block", "over-cap"),
        (1, 36, "review", "cohesion"),
        (2, 75, "review", "cohesion"),
        (2, 76, "review", "cohesion-strict"),
        (2, 100, "review", "cohesion-strict"),
        (2, 101, "block", "over-cap"),
    ],
)
def test_three_or_more_code_files_lose_the_larger_cap(
    files: int, lines: int, verdict: str, band: str
) -> None:
    budget: Budget = code_budget(files=files, lines=lines)

    assert budget.verdict == verdict
    assert budget.band == band


@pytest.mark.parametrize(
    ("lines", "verdict"),
    [(100, "pass"), (101, "review"), (150, "review"), (151, "block")],
)
def test_prose_past_its_own_target_asks_for_review(lines: int, verdict: str) -> None:
    report: SizeReport = measure(
        diff_text=_diff(path="skills/thing/SKILL.md", added=lines)
    )

    assert report.prose.verdict == verdict
    assert report.code.verdict == "pass"
    assert report.verdict == verdict


def test_a_change_is_only_as_good_as_its_worst_budget() -> None:
    report: SizeReport = measure(
        diff_text=_diff(path="cart.py", added=SMALL_CHANGE)
        + _diff(path="README.md", added=200)
        + _diff(path="tests/test_cart.py", added=BIG_CHANGE)
    )

    assert report.code.verdict == "pass"
    assert report.verdict == "block"
    assert report.tests.lines == BIG_CHANGE


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


def test_the_shell_asks_git_for_the_diff_between_base_and_head() -> None:
    git: FakeGit = FakeGit(diff=_diff(path="cart.py", added=SMALL_CHANGE))

    report: SizeReport = report_for(
        base="origin/main", head="HEAD", repo="/repo", run=git
    )

    assert report.code.lines == SMALL_CHANGE
    assert git.calls[0][:3] == ("git", "-C", "/repo")
    assert git.calls[0][-1] == "origin/main...HEAD"


def test_the_shell_reads_rust_post_images_so_inline_tests_are_excluded() -> None:
    path: str = "src/cart.rs"
    git: FakeGit = FakeGit(
        diff=_whole_file_diff(path=path, content=RUST_WITH_INLINE_TESTS),
        sources={path: RUST_WITH_INLINE_TESTS},
    )

    report: SizeReport = report_for(base="main", head="HEAD", repo="/repo", run=git)

    assert report.code.lines == RUST_CODE_LINES
    assert ("git", "-C", "/repo", "show", f"HEAD:{path}") in git.calls


def _spread(*, files: int, lines: int) -> str:
    """A diff over `files` code files carrying `lines` added lines between them."""
    each: list[int] = [1] * files
    each[0] += lines - files
    return "".join(
        _diff(path=f"src/module{index}.py", added=added)
        for index, added in enumerate(each)
    )


def test_the_report_is_printed_as_json_and_the_verdict_is_the_exit_code(
    capsys: pytest.CaptureFixture[str],
) -> None:
    git: FakeGit = FakeGit(diff=_spread(files=4, lines=60))

    exit_code: int = run_cli(base="origin/main", head="HEAD", repo=".", run=git)

    payload: dict[str, object] = json.loads(capsys.readouterr().out)
    assert exit_code == 2
    assert payload["verdict"] == "block"
    assert payload["code"] == {
        "files": 4,
        "lines": 60,
        "target": 35,
        "cap": 50,
        "band": "over-cap",
        "verdict": "block",
    }
    assert str(payload["summary"]).startswith(
        "block: code 60 added lines across 4 file(s)"
    )


def test_an_unmeasurable_change_exits_non_zero_without_a_verdict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    def explode(*, argv: tuple[str, ...]) -> str:
        raise SizeError(f"bad revision: {argv[-1]}")

    exit_code: int = run_cli(base="nope", head="HEAD", repo=".", run=explode)

    assert exit_code not in {0, 1, 2}
    assert capsys.readouterr().out == ""


def test_a_path_the_locale_cannot_encode_exits_without_a_verdict(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An ASCII locale cannot put a non-ASCII path in git's argv — not a verdict."""

    def explode(*, argv: tuple[str, ...]) -> str:
        raise UnicodeEncodeError("ascii", argv[-1], 0, 1, "ordinal not in range(128)")

    exit_code: int = run_cli(base="HEAD~1", head="HEAD", repo=".", run=explode)

    assert exit_code not in {0, 1, 2}
    assert capsys.readouterr().out == ""


def test_an_added_line_that_looks_like_a_header_is_still_counted() -> None:
    """git renders an added line `++ x` as `+++ x`; only a paired header ends a file."""
    diff_text: str = (
        "diff --git a/notes.py b/notes.py\n"
        "--- a/notes.py\n"
        "+++ b/notes.py\n"
        "@@ -0,0 +1,3 @@\n"
        "+++ quoting a diff header\n"
        "+real = 1\n"
        "+also_real = 2\n"
    )

    assert added_line_numbers(diff_text=diff_text) == {"notes.py": (1, 2, 3)}


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


def test_every_lockfile_flavour_is_generated_not_code() -> None:
    flavours: tuple[str, ...] = (
        "pnpm-lock.yaml",
        "package-lock.json",
        "uv.lock",
        "bun.lockb",
        "packages.lock.json",
        "gradle.lockfile",
        "go.work.sum",
        ".terraform.lock.hcl",
    )
    for path in flavours:
        assert classify(path=path) is FileKind.GENERATED, path


RUST_UNBALANCED_TEST_MOD: Final[str] = """\
#[cfg(test)]
mod tests {
    #[test]
    fn multiline_raw_string() {
        let expected = r#"
{ a brace no line-local strip can see
"#;
        assert!(render() == expected);
    }
}

pub fn render() -> String {
    String::new()
}
"""


def test_an_unclosable_test_module_stops_at_the_modules_own_closing_brace() -> None:
    """A multi-line raw string can hide a brace; code below the mod is still code."""
    path: str = "src/lib.rs"

    files: tuple[ChangedFile, ...] = changed_files(
        diff_text=_whole_file_diff(path=path, content=RUST_UNBALANCED_TEST_MOD),
        sources={path: RUST_UNBALANCED_TEST_MOD},
    )

    assert files[0].test_lines == 10
    assert files[0].lines == 4


RUST_SPACED_CLOSE: Final[str] = (
    "#[cfg(test)]\nmod tests {\n    fn hidden() {\n"
    '        let raw = r#"\n{ hidden brace\n"#;\n'
    "    }\n} // end of tests\n\npub fn one() -> u32 {\n    1\n}\n"
)


def test_a_test_module_stops_at_a_close_at_its_own_indent() -> None:
    """A close can carry a trailing comment; the region still ends there, not later."""
    path: str = "src/lib.rs"

    files: tuple[ChangedFile, ...] = changed_files(
        diff_text=_whole_file_diff(path=path, content=RUST_SPACED_CLOSE),
        sources={path: RUST_SPACED_CLOSE},
    )

    assert files[0].lines == 4


def test_a_removed_line_that_looks_like_a_header_does_not_end_the_file() -> None:
    """Only a `---`/`+++` pair naming a path is a header; look-alike content is not."""
    diff_text: str = (
        "diff --git a/notes.md b/notes.md\n"
        "--- a/notes.md\n"
        "+++ b/notes.md\n"
        "@@ -1,1 +1,3 @@\n"
        "--- old marker\n"
        "+++ b/tests/free.py\n"
        "+extra one\n"
        "+extra two\n"
    )

    assert len(added_line_numbers(diff_text=diff_text)["notes.md"]) == 3


@pytest.mark.parametrize(
    ("source", "code_lines"),
    [
        ("#[test]\nfn placeholder() {}\npub fn one() -> u32 {\n    1\n}\n", 3),
        ("#[cfg(test)]\nuse a::{\n    b,\n};\npub fn one() -> u32 {\n    1\n}\n", 3),
        (
            # a `;` inside the type ends this one at the attribute — early, which
            # charges its two remaining lines to code, never the reverse
            "#[cfg(test)]\nconst C: [u8; 1] = [\n    0,\n];\n"
            "pub fn one() -> u32 {\n    1\n}\n",
            5,
        ),
    ],
)
def test_a_test_item_ends_where_its_own_braces_close(
    source: str, code_lines: int
) -> None:
    """A one-line body and a `};` close the item they opened; an unreadable shape
    ends early, charging its lines to code."""
    path: str = "src/lib.rs"

    files: tuple[ChangedFile, ...] = changed_files(
        diff_text=_whole_file_diff(path=path, content=source), sources={path: source}
    )

    assert files[0].lines == code_lines


RUST_ATTRIBUTE_IN_A_STRING: Final[str] = (
    'const EXPECTED: &str = "\n#[cfg(test)]\nmod tests {\n";\n'
    "pub fn parse() -> u32 {\n    1\n}\n"
)


def test_a_test_attribute_inside_a_string_cannot_claim_the_code_after_it() -> None:
    """The region stops at the next top-level item, whatever the braces did."""
    path: str = "src/lib.rs"

    files: tuple[ChangedFile, ...] = changed_files(
        diff_text=_whole_file_diff(path=path, content=RUST_ATTRIBUTE_IN_A_STRING),
        sources={path: RUST_ATTRIBUTE_IN_A_STRING},
    )

    assert files[0].lines == 4


def test_the_printed_report_matches_its_schema(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The schema is the report's contract; nothing else pins the emitter to it."""
    git: FakeGit = FakeGit(diff=_spread(files=4, lines=60))

    run_cli(base="origin/main", head="HEAD", repo=".", run=git)

    payload: dict[str, object] = json.loads(capsys.readouterr().out)
    assert (
        errors_against(
            instance=payload, schema_path=SCHEMAS / "size-report.schema.json"
        )
        == []
    )


def test_a_test_file_with_inline_tests_is_counted_once() -> None:
    """`tests/` files and `#[cfg(test)]` blocks are one tally, not two."""
    path: str = "tests/integration.rs"
    source: str = "use crate::x;\n\n#[test]\nfn works() {\n    assert!(true);\n}\n"

    report: SizeReport = measure(
        diff_text=_whole_file_diff(path=path, content=source), sources={path: source}
    )

    assert report.tests.files == 1
    assert report.tests.lines == len(source.splitlines())


def test_click_command_parses_options_and_propagates_the_exit_code(
    tmp_path: Path,
) -> None:
    """The decorator wiring itself: run_cli tests bypass click's parsing."""
    result: Result = CliRunner().invoke(
        cli, ["--base", "nope", "--repo", str(tmp_path)]
    )

    assert result.exit_code == 3
    assert "error:" in result.output


def test_click_command_requires_a_base() -> None:
    result: Result = CliRunner().invoke(cli, [])

    assert result.exit_code == 2
    assert "--base" in result.output


def test_a_line_git_cannot_decode_still_counts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A latin-1 line is still a line — decoding must not cost the gate its verdict."""
    repo: Path = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run([*_COMMIT, "--allow-empty", "-m", "base"], cwd=repo, check=True)
    (repo / "latin1.txt").write_bytes(b"caf\xe9 not utf-8\n")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    subprocess.run([*_COMMIT, "-m", "add latin-1"], cwd=repo, check=True)

    code: int = run_cli(base="HEAD~1", head="HEAD", repo=str(repo))

    assert code == 0
    payload: dict[str, object] = json.loads(capsys.readouterr().out)
    assert payload["code"] == {
        "files": 1,
        "lines": 1,
        "target": 35,
        "cap": 100,
        "band": "target",
        "verdict": "pass",
    }


def test_a_path_with_a_space_keeps_its_own_suffix() -> None:
    """git pads such a post-image with a TAB; the suffix decides the budget class."""
    diff_text: str = (
        "diff --git a/my docs/read me.md b/my docs/read me.md\n"
        "--- /dev/null\n"
        "+++ b/my docs/read me.md\t\n"
        "@@ -0,0 +1 @@\n"
        "+one\n"
    )

    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text)

    assert files == (
        ChangedFile(
            path="my docs/read me.md", kind=FileKind.PROSE, lines=1, test_lines=0
        ),
    )


def test_a_quoted_path_is_its_own_file() -> None:
    """git C-quotes a path holding `"`; unread, its lines fall to the file before it."""
    diff_text: str = (
        "diff --git a/plain.py b/plain.py\n"
        "--- /dev/null\n"
        "+++ b/plain.py\n"
        "@@ -0,0 +1 @@\n"
        "+a = 1\n"
        'diff --git "a/has\\"quote.py" "b/has\\"quote.py"\n'
        "--- /dev/null\n"
        '+++ "b/has\\"quote.py"\n'
        "@@ -0,0 +1 @@\n"
        "+b = 2\n"
    )

    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text)

    assert [(file.path, file.lines) for file in files] == [
        ("plain.py", 1),
        ('has"quote.py', 1),
    ]


def test_a_quoted_path_can_also_be_tab_padded() -> None:
    """git quotes AND pads when a path holds both a quote and a space."""
    diff_text: str = (
        'diff --git "a/guide for \\"v2\\".md" "b/guide for \\"v2\\".md"\n'
        "--- /dev/null\n"
        '+++ "b/guide for \\"v2\\".md"\t\n'
        "@@ -0,0 +1 @@\n"
        "+one\n"
    )

    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text)

    assert files == (
        ChangedFile(
            path='guide for "v2".md', kind=FileKind.PROSE, lines=1, test_lines=0
        ),
    )


def test_a_quoted_path_keeps_characters_latin_1_cannot_hold() -> None:
    """The escapes are ASCII; the bytes around them are UTF-8 and must survive."""
    diff_text: str = (
        'diff --git "a/中\\"文.py" "b/中\\"文.py"\n'
        "--- /dev/null\n"
        '+++ "b/中\\"文.py"\n'
        "@@ -0,0 +1 @@\n"
        "+x = 1\n"
    )

    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text)

    assert [file.path for file in files] == ['中"文.py']


def test_a_block_whose_header_never_parsed_is_not_a_pass() -> None:
    """A gate that cannot read a block must say so, not report the diff as empty."""
    diff_text: str = (
        "diff --git a/real.py w/real.py\n"
        "--- /dev/null\n"
        "+++ w/real.py\n"
        "@@ -0,0 +1 @@\n"
        "+x = 1\n"
    )

    with pytest.raises(SizeError):
        changed_files(diff_text=diff_text)


def test_a_block_git_writes_without_a_header_is_not_an_error() -> None:
    """A rename, a mode change and a binary each have no `+++` and no lines to read."""
    diff_text: str = (
        "diff --git a/x.py b/y.py\n"
        "similarity index 100%\n"
        "rename from x.py\n"
        "rename to y.py\n"
        "diff --git a/blob.bin b/blob.bin\n"
        "old mode 100644\n"
        "new mode 100755\n"
        "diff --git a/seed.bin b/seed.bin\n"
        "index 1234567..89abcde 100644\n"
        "Binary files a/seed.bin and b/seed.bin differ\n"
        "diff --git a/new.py b/new.py\n"
        "--- /dev/null\n"
        "+++ b/new.py\n"
        "@@ -0,0 +1 @@\n"
        "+new = 1\n"
    )

    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text)

    assert files == (
        ChangedFile(path="new.py", kind=FileKind.CODE, lines=1, test_lines=0),
    )


def test_an_added_line_imitating_a_quoted_header_is_still_counted() -> None:
    """`++ "b/z\\z"` renders as `+++ "b/z\\z"`; a malformed escape is not a header."""
    diff_text: str = (
        "diff --git a/notes.py b/notes.py\n"
        "--- a/notes.py\n"
        "+++ b/notes.py\n"
        "@@ -0,0 +1,2 @@\n"
        '+++ "b/z\\z"\n'
        "+real = 1\n"
    )

    files: tuple[ChangedFile, ...] = changed_files(diff_text=diff_text)

    assert files == (
        ChangedFile(path="notes.py", kind=FileKind.CODE, lines=2, test_lines=0),
    )
