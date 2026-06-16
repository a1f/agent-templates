from pathlib import Path
from typing import Final

# installer/tests/ -> installer/ -> repo root, which holds skills/ plus the canonical
# rules/, gates/, schemas/, scripts/.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_SKILLS_ROOT: Final[Path] = _REPO_ROOT / "skills"

# Skills that bundle repo assets inside their own directory so the assets travel with
# the skill on install (the CLI copies only the skill dir; anything resolved from a repo
# checkout at runtime would silently go missing elsewhere). Maps skill -> asset dir ->
# what it mirrors: the full-mirror marker means the bundle equals the whole canonical
# dir byte-for-byte; a tuple means the bundle holds exactly those files (used when the
# canonical dir carries more than the skill needs, e.g. scripts/ also has a venv).
_FULL_MIRROR: Final[str] = "*"
_BUNDLES: Final[dict[str, dict[str, str | tuple[str, ...]]]] = {
    "make-pr-lite": {"rules": _FULL_MIRROR, "gates": _FULL_MIRROR},
    "make-pr": {
        "rules": _FULL_MIRROR,
        "gates": _FULL_MIRROR,
        "schemas": _FULL_MIRROR,
        "scripts": ("validate_return.py",),
    },
    "improve-architecture": {"rules": ("design-principles.md",)},
}


def _files_by_name(root: Path) -> dict[str, bytes]:
    """Map each file under root to its bytes, keyed by its path relative to root, so two
    asset trees compare by both filename and content in a single equality check."""
    return {
        str(path.relative_to(root)): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def test_skill_bundles_match_canonical_assets() -> None:
    """Skills bundle their assets in-dir so they ship on install (the CLI copies only
    the skill dir). Guard each bundled file against drifting from its canonical copy:
    a stale bundled rule reaching the agents is the silent failure this prevents."""
    for skill, asset_dirs in _BUNDLES.items():
        for asset_dir, spec in asset_dirs.items():
            canonical: Path = _REPO_ROOT / asset_dir
            bundled: Path = _SKILLS_ROOT / skill / asset_dir
            assert bundled.is_dir(), f"skills/{skill}/{asset_dir}/ is missing"
            if isinstance(spec, str):
                assert _files_by_name(bundled) == _files_by_name(canonical), (
                    f"skills/{skill}/{asset_dir}/ diverged from {asset_dir}/ — "
                    f"re-copy the full canonical set into the skill bundle"
                )
                continue
            assert set(_files_by_name(bundled)) == set(spec), (
                f"skills/{skill}/{asset_dir}/ should hold exactly {sorted(spec)}"
            )
            for name in spec:
                assert (bundled / name).read_bytes() == (
                    canonical / name
                ).read_bytes(), (
                    f"skills/{skill}/{asset_dir}/{name} differs from canonical "
                    f"{asset_dir}/{name} — edit the canonical file, then re-copy it"
                )
