import shutil
from pathlib import Path
from typing import Final

from catalog import Unit

# A real file/dir displaced by linking is moved aside to "<name>.bak" so its
# contents survive the install rather than being clobbered by our symlink.
_BACKUP_SUFFIX: Final[str] = ".bak"


def stage_unit(*, unit: Unit, source: Path, staged_root: Path) -> Path:
    """Lay a unit out under "<kind>/<name>" in a staging area first, so the real
    install can swap a fully-built tree into place instead of writing live."""
    destination: Path = staged_root / unit.kind / unit.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Clear any prior staging of this unit so a re-stage fully supersedes it,
    # leaving no stale files behind, rather than colliding with the old tree.
    if destination.is_dir():
        shutil.rmtree(destination)
    elif destination.exists():
        destination.unlink()
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copyfile(source, destination)
    return destination


def link_unit(*, staged_path: Path, link_path: Path) -> Path:
    """Symlink a staged unit into its live location so it is visible under
    ~/.claude/<kind>/ while ~/.claude/at stays the single source of truth."""
    link_path.parent.mkdir(parents=True, exist_ok=True)
    # A pre-existing real (non-symlink) entry is the user's own data, never a
    # prior install of ours, so preserve it before claiming the path; this also
    # frees the path so symlink_to does not hit an existing entry.
    if link_path.exists() and not link_path.is_symlink():
        backup_path: Path = link_path.with_name(link_path.name + _BACKUP_SUFFIX)
        link_path.replace(backup_path)
    link_path.symlink_to(staged_path)
    return link_path
