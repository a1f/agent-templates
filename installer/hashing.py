import hashlib
from pathlib import Path


def hash_unit(path: Path) -> str:
    """Fingerprint a unit's content as a stable digest so a later run can tell
    whether the file on disk still matches what was installed."""
    if not path.is_dir():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    # Bind each file's content to its relative path, sorted so the digest is
    # independent of traversal order and changes when bytes move to a new path.
    files: list[Path] = sorted(p for p in path.rglob("*") if p.is_file())
    manifest: bytes = b"".join(
        file.relative_to(path).as_posix().encode()
        + b"\0"
        + hashlib.sha256(file.read_bytes()).digest()
        for file in files
    )
    return hashlib.sha256(manifest).hexdigest()
