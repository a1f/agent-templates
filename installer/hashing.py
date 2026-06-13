import hashlib
from pathlib import Path


def hash_unit(path: Path) -> str:
    """Fingerprint a unit's content as a stable digest so a later run can tell
    whether the file on disk still matches what was installed."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
