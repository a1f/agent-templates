from pathlib import Path
from typing import Final

# installer/tests/ -> installer/ -> repo root, which holds skills/, rules/, gates/.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_SKILL_ROOT: Final[Path] = _REPO_ROOT / "skills" / "make-pr-lite"
_BUNDLED_ASSET_DIRS: Final[tuple[str, ...]] = ("rules", "gates")


def _files_by_name(root: Path) -> dict[str, bytes]:
    """Map each file under root to its bytes, keyed by its path relative to root, so
    two asset trees compare by both filename and content in a single equality check."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_make_pr_lite_bundles_canonical_rules_and_gates() -> None:
    """make-pr-lite ships its own rules/ and gates/ so they travel with the skill on
    install — the CLI copies only the skill directory. Guard the bundle against
    drifting from the repo's canonical copies: a stale bundled rule is exactly the
    failure this bundle prevents — a language rule never reaching the agents."""
    for subdir in _BUNDLED_ASSET_DIRS:
        canonical: dict[str, bytes] = _files_by_name(_REPO_ROOT / subdir)
        bundled: dict[str, bytes] = _files_by_name(_SKILL_ROOT / subdir)
        assert bundled == canonical, (
            f"skills/make-pr-lite/{subdir}/ diverged from {subdir}/ — edit the "
            f"canonical file, then re-copy the full set into the skill bundle"
        )
