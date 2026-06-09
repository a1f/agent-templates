import shutil
from pathlib import Path

from catalog import Unit


def stage_unit(*, unit: Unit, source: Path, staged_root: Path) -> Path:
    """Lay a unit out under "<kind>/<name>" in a staging area first, so the real
    install can swap a fully-built tree into place instead of writing live."""
    destination: Path = staged_root / unit.kind / unit.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    return destination
