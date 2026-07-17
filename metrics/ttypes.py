"""Shared data shapes for the metrics package (named ttypes: types shadows stdlib)."""

from dataclasses import dataclass
from typing import Self


@dataclass
class RoleUsage:
    """Running token and cost totals for a set of attributed messages."""

    tok_output: int = 0
    tok_cache_read: int = 0
    tok_cache_creation: int = 0
    est_cost_usd: float = 0.0

    def add(self, *, other: Self) -> None:
        """Fold another total in so one contribution can feed several tallies."""
        self.tok_output += other.tok_output
        self.tok_cache_read += other.tok_cache_read
        self.tok_cache_creation += other.tok_cache_creation
        self.est_cost_usd += other.est_cost_usd
