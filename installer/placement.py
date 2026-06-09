import shutil
from pathlib import Path

from catalog import Unit


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
