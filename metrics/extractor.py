"""Turn a Claude Code session transcript into one run-level metrics row."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

_TRACKED_VARIANTS: Final[frozenset[str]] = frozenset({"make-pr"})


@dataclass(frozen=True)
class RunRecord:
    """One flattened metrics row for a single attributed agent run.

    The field list is the record's declared public interface. Later extraction
    cycles fill the token, cost, dispatch, and outcome columns; every field
    defaults so an early cycle can leave the rest unset.
    """

    run_id: str = ""
    session_id: str = ""
    project: str = ""
    repo: str = ""
    variant: str = ""
    skill_version: str = ""
    started_at: datetime | None = None
    tok_output: int = 0
    tok_cache_read: int = 0
    tok_cache_creation: int = 0
    est_cost_usd: float = 0.0
    active_sec: float = 0.0
    n_dispatches: int = 0
    n_fix_loops: int = 0
    outcome: str = ""
    blocked_reason: str = ""
    pr_number: int | None = None
    pr_url: str = ""
    detail: dict[str, object] = field(default_factory=dict)


def extract_run(*, transcript_path: Path) -> RunRecord | None:
    """Read a JSONL transcript into its run record, or None for an untracked run.

    Streams line by line so header lines that lack `attributionSkill`/`timestamp` are
    tolerated. A run is attributed only when its `attributionSkill` is in
    `_TRACKED_VARIANTS`; `started_at` is the earliest `timestamp` anywhere in the file.
    """
    earliest_at: datetime | None = None
    variant: str | None = None
    session_id: str = ""
    with transcript_path.open(encoding="utf-8") as lines:
        for line in lines:
            entry: dict[str, object] = json.loads(line)
            timestamp: object = entry.get("timestamp")
            if isinstance(timestamp, str):
                seen_at: datetime = datetime.fromisoformat(timestamp)
                if earliest_at is None or seen_at < earliest_at:
                    earliest_at = seen_at
            skill: object = entry.get("attributionSkill")
            if (
                variant is None
                and isinstance(skill, str)
                and skill in _TRACKED_VARIANTS
            ):
                variant = skill
                identifier: object = entry.get("session_id")
                session_id = identifier if isinstance(identifier, str) else ""
    if variant is None:
        return None
    return RunRecord(variant=variant, session_id=session_id, started_at=earliest_at)
