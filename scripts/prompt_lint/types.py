"""The vocabulary the checks speak: a catalog row resolved to the path it stands for."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class RegisteredUnit:
    """A [[units]] row, carrying the path in the prompt tree that it stands for."""

    kind: str
    name: str
    path: str
