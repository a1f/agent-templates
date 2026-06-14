import difflib
import hashlib
import json
from pathlib import Path
from typing import Final

_CLAUDE_DIRNAME: Final[str] = ".claude"
# The install-state file is re-serialized canonically (sorted keys, compact
# separators) so a golden pins the state's meaning rather than the byte order the
# installer happened to write it in.
_STATE_RELPATH: Final[str] = ".claude/at/state.json"


def _descendants(directory: Path) -> list[Path]:
    """Collect every entry beneath a directory while treating a symlink as a leaf,
    so the snapshot records a link once instead of crossing into the tree it
    targets (and looping or double-counting staged files)."""
    found: list[Path] = []
    for child in directory.iterdir():
        found.append(child)
        # is_symlink before is_dir: a symlink to a directory reports is_dir() true,
        # yet it must stay a leaf so traversal never follows it.
        if not child.is_symlink() and child.is_dir():
            found.extend(_descendants(child))
    return found


def _render_entry(*, entry: Path, home: Path) -> str:
    """Render one tree entry as a single normalized line keyed on its home-relative
    POSIX path, so a golden stays independent of where home sits on disk."""
    relpath: str = entry.relative_to(home).as_posix()
    if entry.is_symlink():
        target: Path = entry.readlink()
        # Rewrite a target that lands inside home to a home-relative POSIX path so
        # it survives relocation; a target pointing elsewhere is shown verbatim.
        try:
            shown: str = target.relative_to(home).as_posix()
        except ValueError:
            shown = str(target)
        return f"link {relpath} -> {shown}"
    if entry.is_dir():
        return f"dir {relpath}"
    if relpath == _STATE_RELPATH:
        parsed: object = json.loads(entry.read_text(encoding="utf-8"))
        canonical: str = json.dumps(parsed, sort_keys=True, separators=(",", ":"))
        return f"json {relpath} {canonical}"
    digest: str = hashlib.sha256(entry.read_bytes()).hexdigest()
    return f"file {relpath} {digest}"


def snapshot(home: Path) -> str:
    """Exists so e2e scenarios can diff an installed tree against its golden.

    The block is sorted by each entry's home-relative POSIX path and newline-
    terminated, so an identical tree always renders to identical text regardless of
    filesystem traversal order or where home lives."""
    entries: list[Path] = _descendants(home / _CLAUDE_DIRNAME)
    entries.sort(key=lambda entry: entry.relative_to(home).as_posix())
    lines: list[str] = [_render_entry(entry=entry, home=home) for entry in entries]
    return "\n".join(lines) + "\n"


def assert_matches_golden(*, name: str, actual: str, goldens_dir: Path) -> None:
    """Gate an e2e scenario's output against its committed golden so drift fails
    loudly with a diff and a pointer to AT_BLESS, instead of passing silently."""
    golden_path: Path = goldens_dir / f"{name}.golden"
    golden: str = golden_path.read_text(encoding="utf-8")
    if actual == golden:
        return
    diff: str = "\n".join(
        difflib.unified_diff(
            golden.splitlines(),
            actual.splitlines(),
            fromfile=f"{name}.golden",
            tofile="actual",
            lineterm="",
        )
    )
    raise AssertionError(
        f"snapshot does not match golden {name!r}; "
        f"re-run with AT_BLESS=1 to regenerate it.\n{diff}"
    )
