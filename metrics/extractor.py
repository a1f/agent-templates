"""Turn a Claude Code session transcript into one run-level metrics row."""

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from itertools import pairwise
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

# The critic subagent's verdict enum; the last such verdict seen sets the run outcome.
_CRITIC_VERDICTS: Final[frozenset[str]] = frozenset(
    {"achieved", "partial", "not_achieved"}
)

# The coder return schemas in this pipeline; both carry status/blocked_reason with
# identical semantics, so a blocked return from either records the run's friction.
_CODER_ROLES: Final[frozenset[str]] = frozenset({"coder", "coder-lite"})

# The dispatch tool's current and legacy names; a tool_use part with either name is
# a subagent dispatch. Such a dispatch counts as a fix loop when its prompt's first
# line declares fix mode (the whole word `fix`, not `mode: build`/`green`/etc.).
_DISPATCH_TOOLS: Final[frozenset[str]] = frozenset({"Agent", "Task"})
_FIX_MODE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*mode:\s*fix\b", re.IGNORECASE)

# A tracked run whose scan found neither a critic verdict nor a coder block degrades
# to this outcome rather than an empty string, so every tracked run carries a signal.
_UNKNOWN_OUTCOME: Final[str] = "unknown"

# Consecutive line timestamps farther apart than this are the user away from the
# session, not the run working, so that gap is excluded from active_sec.
_IDLE_GAP_SEC: Final[float] = 300.0


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


def _leaf_texts(*, value: object) -> Iterator[str]:
    """Yield the text a content leaf carries: a plain string, or a list's text parts."""
    if isinstance(value, str):
        yield value
        return
    if isinstance(value, list):
        for part in value:
            if isinstance(part, dict) and part.get("type") == "text":
                text: object = part.get("text")
                if isinstance(text, str):
                    yield text


def _text_pieces(*, message: dict[str, object]) -> Iterator[str]:
    """Yield every text a subagent return could occupy, skipping tool_use inputs."""
    content: object = message.get("content")
    yield from _leaf_texts(value=content)
    if isinstance(content, list):
        for part in content:
            if isinstance(part, dict) and part.get("type") == "tool_result":
                yield from _leaf_texts(value=part.get("content"))


def _dispatch_declares_fix(*, part: object) -> bool:
    """Report whether a content part is a subagent dispatch declaring fix mode.

    A missing or malformed part, tool name, input dict, or prompt is simply not a
    fix loop rather than an error; only a dispatch tool_use whose `input.prompt`
    first line matches `_FIX_MODE_RE` counts.
    """
    if not isinstance(part, dict) or part.get("type") != "tool_use":
        return False
    if part.get("name") not in _DISPATCH_TOOLS:
        return False
    payload: object = part.get("input")
    if not isinstance(payload, dict):
        return False
    prompt: object = payload.get("prompt")
    if not isinstance(prompt, str):
        return False
    first_line: str = prompt.split("\n", 1)[0]
    return _FIX_MODE_RE.match(first_line) is not None


def _count_fix_dispatches(*, message: dict[str, object]) -> int:
    """Count the fix-mode subagent dispatches carried in a message's content."""
    content: object = message.get("content")
    if not isinstance(content, list):
        return 0
    return sum(1 for part in content if _dispatch_declares_fix(part=part))


def _parse_return(*, text: str) -> dict[str, object] | None:
    """Parse a text piece into its embedded JSON object, or None when it holds none."""
    stripped: str = text.strip()
    try:
        parsed: object = json.loads(stripped)
    except json.JSONDecodeError:
        start: int = stripped.find("{")
        if start == -1:
            return None
        try:
            parsed = json.JSONDecoder().raw_decode(stripped, start)[0]
        except json.JSONDecodeError:
            return None
    return parsed if isinstance(parsed, dict) else None


def _active_sec(*, timestamps: list[datetime]) -> float:
    """Sum the seconds between consecutive line timestamps, dropping idle gaps.

    Timestamps are sorted first, so the total is independent of the order lines
    were read; a gap wider than `_IDLE_GAP_SEC` is excluded. Fewer than two
    timestamps leave no gap and yield 0.0.
    """
    ordered: list[datetime] = sorted(timestamps)
    total: float = 0.0
    for earlier, later in pairwise(ordered):
        gap: float = (later - earlier).total_seconds()
        if gap <= _IDLE_GAP_SEC:
            total += gap
    return total


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
    `_TRACKED_VARIANTS`; `started_at` is the earliest `timestamp` anywhere in the file
    and `active_sec` sums the non-idle gaps between all parsed timestamps.
    """
    line_timestamps: list[datetime] = []
    variant: str | None = None
    session_id: str = ""
    seen_message_ids: set[str] = set()
    tok_output: int = 0
    tok_cache_read: int = 0
    tok_cache_creation: int = 0
    est_cost_usd: float = 0.0
    n_fix_loops: int = 0
    outcome: str = ""
    blocked_reason: str | None = None
    with transcript_path.open(encoding="utf-8") as lines:
        for line in lines:
            entry: dict[str, object] = json.loads(line)
            timestamp: object = entry.get("timestamp")
            if isinstance(timestamp, str):
                try:
                    seen_at: datetime = datetime.fromisoformat(timestamp)
                except ValueError:
                    pass  # an unparsable timestamp means no timestamp on this line
                else:
                    line_timestamps.append(seen_at)
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
            # Scan content before the usage bookkeeping: a subagent return rides a
            # user line whose message has no `usage` and would otherwise be skipped.
            for piece in _text_pieces(message=message):
                parsed: dict[str, object] | None = _parse_return(text=piece)
                if parsed is None:
                    continue
                role: object = parsed.get("role")
                if role == "critic":
                    verdict: object = parsed.get("verdict")
                    if isinstance(verdict, str) and verdict in _CRITIC_VERDICTS:
                        outcome = verdict
                elif role in _CODER_ROLES and parsed.get("status") == "blocked":
                    reason: object = parsed.get("blocked_reason")
                    blocked_reason = reason if isinstance(reason, str) else ""
            # A fix-mode dispatch rides a tool_use part the return scan skips, so
            # count it here in the same per-line content pass, not a second read.
            n_fix_loops += _count_fix_dispatches(message=message)
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
    # A critic verdict wins; absent one a coder block records "blocked", and a run
    # with neither signal degrades to "unknown" rather than an empty outcome.
    if outcome == "":
        outcome = "blocked" if blocked_reason is not None else _UNKNOWN_OUTCOME
    started_at: datetime | None = min(line_timestamps) if line_timestamps else None
    return RunRecord(
        variant=variant,
        session_id=session_id,
        started_at=started_at,
        active_sec=_active_sec(timestamps=line_timestamps),
        tok_output=tok_output,
        tok_cache_read=tok_cache_read,
        tok_cache_creation=tok_cache_creation,
        est_cost_usd=est_cost_usd,
        n_fix_loops=n_fix_loops,
        outcome=outcome,
        blocked_reason=blocked_reason if blocked_reason is not None else "",
        detail={"pricing_version": _PRICING_VERSION},
    )
