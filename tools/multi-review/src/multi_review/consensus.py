"""Merge and deduplicate findings across models by file+line proximity."""

import structlog

from multi_review.constants import LINE_PROXIMITY_THRESHOLD, SEVERITY_ORDER
from multi_review.types import Finding, MergedFinding, Severity

logger = structlog.get_logger()


def merge_findings(*, findings: list[Finding]) -> list[MergedFinding]:
    """Group findings by file+line proximity, merge, and sort by severity."""
    if not findings:
        return []

    groups = _group_by_proximity(findings)
    merged = [_merge_group(group) for group in groups]
    return _sort_findings(merged)


def _group_by_proximity(
    findings: list[Finding],
) -> list[list[Finding]]:
    """Group findings within LINE_PROXIMITY_THRESHOLD lines in the same file."""
    sorted_findings = sorted(findings, key=lambda f: (f.file, f.line))

    groups: list[list[Finding]] = []
    current_group: list[Finding] = []

    for finding in sorted_findings:
        if not current_group:
            current_group.append(finding)
            continue

        anchor = current_group[0]
        same_file = finding.file == anchor.file
        close_line = abs(finding.line - anchor.line) <= LINE_PROXIMITY_THRESHOLD

        if same_file and close_line:
            current_group.append(finding)
        else:
            groups.append(current_group)
            current_group = [finding]

    if current_group:
        groups.append(current_group)

    return groups


def _merge_group(group: list[Finding]) -> MergedFinding:
    """Merge a group of proximate findings into a single MergedFinding."""
    highest_severity = max(
        (f.severity for f in group),
        key=lambda s: SEVERITY_ORDER[s],
    )

    models = tuple(sorted({f.model_name for f in group}))
    descriptions = tuple(dict.fromkeys(f.issue for f in group))
    categories = {f.category for f in group}

    anchor = min(group, key=lambda f: f.line)

    return MergedFinding(
        file=anchor.file,
        line=anchor.line,
        issue=descriptions[0] if len(descriptions) == 1 else " | ".join(descriptions),
        severity=highest_severity,
        category=sorted(categories)[0],
        models=models,
        descriptions=descriptions,
    )


def _sort_findings(findings: list[MergedFinding]) -> list[MergedFinding]:
    """Sort by severity DESC, then agreement count DESC."""
    return sorted(
        findings,
        key=lambda f: (SEVERITY_ORDER[f.severity], len(f.models)),
        reverse=True,
    )


def severity_label(*, severity: Severity) -> str:
    """Human-readable severity label with icon."""
    labels = {
        Severity.CRITICAL: "CRITICAL",
        Severity.MAJOR: "MAJOR",
        Severity.MINOR: "MINOR",
        Severity.LOW: "LOW",
    }
    return labels[severity]
