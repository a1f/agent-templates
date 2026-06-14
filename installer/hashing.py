import hashlib
from dataclasses import dataclass
from pathlib import Path


def hash_unit(path: Path) -> str:
    """Fingerprint a unit's content as a stable digest so a later run can tell
    whether the file on disk still matches what was installed."""
    if not path.is_dir():
        return hashlib.sha256(path.read_bytes()).hexdigest()
    # Bind each file's content to its relative path, sorted by that same
    # canonical relative-posix key so the sort agrees with the emitted key on
    # every platform: the digest stays independent of traversal order (and of
    # platform path-casing) and still changes when bytes move to a new path.
    files: list[Path] = sorted(
        (p for p in path.rglob("*") if p.is_file()),
        key=lambda p: p.relative_to(path).as_posix(),
    )
    manifest: bytes = b"".join(
        file.relative_to(path).as_posix().encode()
        + b"\0"
        + hashlib.sha256(file.read_bytes()).digest()
        for file in files
    )
    return hashlib.sha256(manifest).hexdigest()


@dataclass(frozen=True)
class Drift:
    """Separates the two independent axes of divergence so a caller can tell an
    upstream update apart from a local edit."""

    upstream_changed: bool
    locally_edited: bool


def detect_drift(*, source: Path, staged: Path, recorded: str) -> Drift:
    """Reports how an installed unit diverges from its recorded install-time hash
    so a reconcile step can choose between updating it and preserving it."""
    return Drift(
        upstream_changed=hash_unit(source) != recorded,
        locally_edited=hash_unit(staged) != recorded,
    )
