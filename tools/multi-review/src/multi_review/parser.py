"""Extract structured findings JSON from raw model output."""

import json
import re

import structlog

from multi_review.exceptions import ParseError
from multi_review.types import Finding, Severity

logger = structlog.get_logger()

_CODE_FENCE_RE = re.compile(
    r"```(?:json)?\s*\n(.*?)```",
    re.DOTALL,
)


def parse_findings(*, raw_output: str, model_name: str) -> list[Finding]:
    """Parse model output into Finding objects using 3-tier strategy."""
    data = _extract_json_array(raw=raw_output, model_name=model_name)
    return _validate_findings(data=data, model_name=model_name)


def _extract_json_array(*, raw: str, model_name: str) -> list[dict[str, object]]:
    """Try direct parse, then code fence regex, then line scan."""
    stripped = raw.strip()

    # Strategy 1: direct JSON parse
    result = _try_direct_parse(stripped)
    if result is not None:
        logger.debug("parse_strategy", model=model_name, strategy="direct")
        return result

    # Strategy 2: regex code fence extraction
    result = _try_code_fence(stripped)
    if result is not None:
        logger.debug("parse_strategy", model=model_name, strategy="code_fence")
        return result

    # Strategy 3: line-by-line scan for JSON array
    result = _try_line_scan(stripped)
    if result is not None:
        logger.debug("parse_strategy", model=model_name, strategy="line_scan")
        return result

    raise ParseError(
        f"Could not extract JSON findings from {model_name} output "
        f"({len(stripped)} chars)"
    )


def _try_direct_parse(text: str) -> list[dict[str, object]] | None:
    """Attempt to parse entire text as JSON array."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None
    if isinstance(parsed, list):
        return parsed  # type: ignore[return-value]
    return None


def _try_code_fence(text: str) -> list[dict[str, object]] | None:
    """Extract JSON from markdown code fences."""
    for match in _CODE_FENCE_RE.finditer(text):
        content = match.group(1).strip()
        result = _try_direct_parse(content)
        if result is not None:
            return result
    return None


def _try_line_scan(text: str) -> list[dict[str, object]] | None:
    """Scan for a JSON array by finding matching [ ] brackets."""
    start = text.find("[")
    if start == -1:
        return None

    depth = 0
    for i in range(start, len(text)):
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                candidate = text[start : i + 1]
                result = _try_direct_parse(candidate)
                if result is not None:
                    return result
                break
    return None


def _validate_findings(
    *,
    data: list[dict[str, object]],
    model_name: str,
) -> list[Finding]:
    """Convert raw dicts to Finding objects, skipping malformed entries."""
    findings: list[Finding] = []
    for i, entry in enumerate(data):
        try:
            finding = Finding(
                file=str(entry["file"]),
                line=int(entry["line"]),  # type: ignore[arg-type]
                issue=str(entry["issue"]),
                severity=Severity(str(entry["severity"]).upper()),
                category=str(entry.get("category", "unknown")),
                model_name=model_name,
            )
            findings.append(finding)
        except (KeyError, ValueError) as exc:
            logger.warning(
                "skipping_malformed_finding",
                model=model_name,
                index=i,
                error=str(exc),
            )
    return findings
