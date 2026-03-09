"""Shared fixtures for multi-review tests."""

import pytest

from multi_review.types import Finding, Severity


@pytest.fixture()
def sample_finding() -> Finding:
    """A single sample finding."""
    return Finding(
        file="src/auth.py",
        line=42,
        issue="SQL injection via unsanitized input",
        severity=Severity.CRITICAL,
        category="security",
        model_name="claude",
    )


@pytest.fixture()
def sample_findings_multi_model() -> list[Finding]:
    """Findings from multiple models with overlapping locations."""
    return [
        Finding(
            file="src/auth.py",
            line=42,
            issue="SQL injection via unsanitized input",
            severity=Severity.CRITICAL,
            category="security",
            model_name="claude",
        ),
        Finding(
            file="src/auth.py",
            line=44,
            issue="Unsanitized SQL query parameter",
            severity=Severity.MAJOR,
            category="security",
            model_name="codex",
        ),
        Finding(
            file="src/utils.py",
            line=10,
            issue="Unused import",
            severity=Severity.LOW,
            category="maintainability",
            model_name="claude",
        ),
        Finding(
            file="src/utils.py",
            line=100,
            issue="O(n^2) loop in data processing",
            severity=Severity.MINOR,
            category="performance",
            model_name="codex",
        ),
    ]
