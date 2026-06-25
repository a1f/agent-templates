import shutil
from pathlib import Path
from typing import Final

from catalog import Unit

# The shared "<name>.bak" convention: an entry about to be overwritten is moved
# aside so its contents survive — a real file displaced by our symlink, or a
# hand-edited staged tree rescued before a re-stage — rather than being clobbered.
_BACKUP_SUFFIX: Final[str] = ".bak"


def _remove_staged_entry(path: Path) -> None:
    """Drop a staged entry without the caller minding its shape — a unit stages
    as a directory tree (skill) or a single file (agent/rule), and an absent path
    is a quiet no-op so re-staging and unstaging share one removal decision."""
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _copy_entry(*, source: Path, destination: Path) -> None:
    """Copy a source entry to destination without the caller minding its shape —
    a directory tree or a single file — so staging a unit and staging an extra
    share one copy decision. copy2 (not copyfile) carries the source's mode across,
    so an executable hook script stays executable once staged — matching copytree."""
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        shutil.copy2(source, destination)


def staged_unit_path(*, unit: Unit, staged_root: Path) -> Path:
    """Own the "<kind>/<name>" staged-layout decision in one place, so callers
    locate a unit's staged copy without re-encoding the path this module lays down."""
    return staged_root / unit.kind / unit.name


def stage_unit(*, unit: Unit, source: Path, staged_root: Path) -> Path:
    """Lay a unit out under "<kind>/<name>" in a staging area first, so the real
    install can swap a fully-built tree into place instead of writing live."""
    destination: Path = staged_unit_path(unit=unit, staged_root=staged_root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Clear any prior staging of this unit so a re-stage fully supersedes it,
    # leaving no stale files behind, rather than colliding with the old tree.
    _remove_staged_entry(destination)
    _copy_entry(source=source, destination=destination)
    return destination


def stage_extra(*, relpath: str, source_root: Path, state_root: Path) -> Path:
    """Copy a package's extra support file or directory to the state root at its
    source-relative path, so a skill finds its schemas and helper scripts where it
    expects them rather than back in the source tree."""
    destination: Path = state_root / relpath
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Clear any prior copy so a re-stage fully supersedes it, leaving no stale
    # files behind, rather than colliding with the old entry.
    _remove_staged_entry(destination)
    _copy_entry(source=source_root / relpath, destination=destination)
    return destination


def unstage_unit(*, unit: Unit, staged_root: Path) -> None:
    """Tear down a unit's staged entry at "<kind>/<name>" so the staging area no
    longer holds it — the inverse of stage_unit, dropping either the directory
    tree or the single file it laid down."""
    staged_path: Path = staged_unit_path(unit=unit, staged_root=staged_root)
    _remove_staged_entry(staged_path)


def unstage_extra(*, relpath: str, state_root: Path) -> None:
    """Tear down an extra's staged copy at its source-relative path so the state
    root no longer holds it — the inverse of stage_extra, dropping either the
    directory tree or the single file it laid down."""
    _remove_staged_entry(state_root / relpath)


def backup_staged_unit(*, unit: Unit, staged_root: Path) -> Path | None:
    """Move a hand-edited staged unit aside to "<name>.bak" so the user's local
    edit survives a following re-stage that overwrites the staged tree, returning
    None when nothing is staged to rescue."""
    staged_path: Path = staged_unit_path(unit=unit, staged_root=staged_root)
    if not staged_path.exists():
        return None
    backup_path: Path = staged_path.with_name(staged_path.name + _BACKUP_SUFFIX)
    _remove_staged_entry(backup_path)  # supersede any prior .bak, idempotently
    staged_path.replace(backup_path)
    return backup_path


def link_unit(*, staged_path: Path, link_path: Path) -> Path:
    """Symlink a staged unit into its live location so it is visible under
    ~/.claude/<kind>/ while ~/.claude/at stays the single source of truth."""
    link_path.parent.mkdir(parents=True, exist_ok=True)
    # An existing symlink is a prior install of ours, so just drop it; only a
    # real (non-symlink) entry is the user's own data worth backing up. Either
    # way the path is freed so symlink_to does not hit an existing entry.
    if link_path.is_symlink():
        link_path.unlink()
    elif link_path.exists():
        backup_path: Path = link_path.with_name(link_path.name + _BACKUP_SUFFIX)
        link_path.replace(backup_path)
    link_path.symlink_to(staged_path)
    return link_path


def unlink_unit(*, link_path: Path) -> None:
    """Remove a unit's live symlink so it is no longer visible under
    ~/.claude/<kind>/, while the staged tree it pointed at survives untouched
    as the single source of truth."""
    # Only a symlink is a prior install of ours to drop; a real entry is the
    # user's own data, so leave it untouched as a quiet no-op — the inverse of
    # link_unit, which likewise treats only a real non-symlink entry as the user's.
    if not link_path.is_symlink():
        return
    # unlink drops the symlink itself, never following it, so the staged target
    # is left in place — the inverse of link_unit's symlink_to.
    link_path.unlink()
    # If linking displaced the user's own file to "<name>.bak", move it back over
    # the now-freed path so the original is restored — inverse of link_unit's backup.
    backup_path: Path = link_path.with_name(link_path.name + _BACKUP_SUFFIX)
    if backup_path.exists():
        backup_path.replace(link_path)
