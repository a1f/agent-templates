"""Turn a Claude Code session transcript into one run-level metrics row."""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

_TRACKED_VARIANTS: Final[frozenset[str]] = frozenset({"make-pr", "make-pr-lite"})

# Anthropic list prices cached 2026-06-24, USD per 1,000,000 tokens as (input, output).
# An unknown model id is absent here and contributes $0 to the cost estimate.
_PRICING_VERSION: Final[str] = "2026-06-24"
_TOKENS_PER_MTOK: Final[int] = 1_000_000
_PER_MTOK_USD: Final[dict[str, tuple[float, float]]] = {
    "claude-fable-5": (10.0, 50.0),
    "claude-mythos-5": (10.0, 50.0),
    "claude-opus-4-8": (5.0, 25.0),
    "claude-opus-4-7": (5.0, 25.0),
    "claude-opus-4-6": (5.0, 25.0),
    "claude-sonnet-5": (3.0, 15.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (1.0, 5.0),
}
# Multipliers on the model's input rate for each way input tokens are billed.
_CACHE_READ_MULT: Final[float] = 0.1
_CACHE_WRITE_5M_MULT: Final[float] = 1.25
_CACHE_WRITE_1H_MULT: Final[float] = 2.0


def _as_int(*, value: object) -> int:
    """Narrow a usage field to int, treating an absent or non-int value as zero."""
    return value if isinstance(value, int) else 0


def _message_cost_usd(*, usage: dict[str, object], model: str) -> float:
    """Price one message's usage, or $0 for a model absent from the pricing table.

    Cache writes bill by TTL from the `cache_creation` breakdown; when that breakdown
    is missing, all `cache_creation_input_tokens` are billed at the 5-minute rate.
    """
    rates: tuple[float, float] | None = _PER_MTOK_USD.get(model)
    if rates is None:
        return 0.0
    input_per_tok: float = rates[0] / _TOKENS_PER_MTOK
    output_per_tok: float = rates[1] / _TOKENS_PER_MTOK

    breakdown: object = usage.get("cache_creation")
    if isinstance(breakdown, dict):
        write_1h: int = _as_int(value=breakdown.get("ephemeral_1h_input_tokens"))
        write_5m: int = _as_int(value=breakdown.get("ephemeral_5m_input_tokens"))
    else:
        write_1h = 0
        write_5m = _as_int(value=usage.get("cache_creation_input_tokens"))

    billed_input: float = (
        _as_int(value=usage.get("input_tokens"))
        + _as_int(value=usage.get("cache_read_input_tokens")) * _CACHE_READ_MULT
        + write_5m * _CACHE_WRITE_5M_MULT
        + write_1h * _CACHE_WRITE_1H_MULT
    )
    output: int = _as_int(value=usage.get("output_tokens"))
    return billed_input * input_per_tok + output * output_per_tok


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
    seen_message_ids: set[str] = set()
    tok_output: int = 0
    tok_cache_read: int = 0
    tok_cache_creation: int = 0
    est_cost_usd: float = 0.0
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
            message: object = entry.get("message")
            if not isinstance(message, dict):
                continue
            usage: object = message.get("usage")
            if not isinstance(usage, dict):
                continue
            message_id: object = message.get("id")
            if isinstance(message_id, str):
                if message_id in seen_message_ids:
                    continue
                seen_message_ids.add(message_id)
            tok_output += _as_int(value=usage.get("output_tokens"))
            tok_cache_read += _as_int(value=usage.get("cache_read_input_tokens"))
            tok_cache_creation += _as_int(
                value=usage.get("cache_creation_input_tokens")
            )
            model: object = message.get("model")
            est_cost_usd += _message_cost_usd(
                usage=usage, model=model if isinstance(model, str) else ""
            )
    if variant is None:
        return None
    return RunRecord(
        variant=variant,
        session_id=session_id,
        started_at=earliest_at,
        tok_output=tok_output,
        tok_cache_read=tok_cache_read,
        tok_cache_creation=tok_cache_creation,
        est_cost_usd=est_cost_usd,
        detail={"pricing_version": _PRICING_VERSION},
    )
