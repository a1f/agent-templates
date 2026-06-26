from pathlib import Path
from typing import Final

from catalog import Catalog, load_catalog
from paths import STATE_ROOT

# installer/tests/ -> installer/ -> repo root, holding skills/<name>/ and the catalog.
_REPO_ROOT: Final[Path] = Path(__file__).resolve().parent.parent.parent
_CATALOG_PATH: Final[Path] = _REPO_ROOT / "installer" / "catalog.toml"
_SKILLS_ROOT: Final[Path] = _REPO_ROOT / "skills"

# The state root the installer stages each package's extras into, in the tilde form a
# SKILL.md writes. Derived from the installer's own STATE_ROOT so the skill text and the
# installer cannot drift: the skill must read extras from the SAME root the installer
# stages them to.
_EXTRAS_ROOT: Final[str] = "~/" + str(STATE_ROOT.relative_to(Path.home()))

# Unit kind whose SKILL.md prompt resolves the package's extras at runtime.
_SKILL_KIND: Final[str] = "skill"


def test_skill_prompts_resolve_package_extras_from_state_root() -> None:
    """A package's extras are staged into the ~/.claude/at state root, so its skill
    units must resolve each extra from that root and not from <skill_root>; driven off
    catalog truth so the check tracks whatever packages declare extras."""
    catalog: Catalog = load_catalog(_CATALOG_PATH)
    checked_pairs: int = 0

    for package in catalog.packages:
        if not package.extras:
            continue
        for unit in package.units:
            if unit.kind != _SKILL_KIND:
                continue
            prompt: str = (_SKILLS_ROOT / unit.name / "SKILL.md").read_text(
                encoding="utf-8"
            )
            for relpath in package.extras:
                staged_ref: str = f"{_EXTRAS_ROOT}/{relpath}"
                stale_root: str = f"<skill_root>/{relpath.split('/')[0]}"
                assert staged_ref in prompt, (
                    f"skill {unit.name!r} must resolve extra {relpath!r} from "
                    f"{staged_ref!r}, the state root the installer stages it into"
                )
                assert stale_root not in prompt, (
                    f"skill {unit.name!r} still resolves extra {relpath!r} from "
                    f"{stale_root!r}; the cutover must replace the <skill_root> "
                    f"reference, not keep it alongside {_EXTRAS_ROOT!r}"
                )
                checked_pairs += 1

    assert checked_pairs > 0, (
        "no (skill, extra) pair was checked — no package declares extras whose units "
        "include a skill, so this test would pass vacuously"
    )
