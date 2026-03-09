"""Tests for multi_review.consensus."""

from multi_review.consensus import merge_findings
from multi_review.types import Finding, Severity


class TestMergeFindings:
    """Tests for grouping, merging, and sorting findings."""

    def test_empty_input(self) -> None:
        assert merge_findings(findings=[]) == []

    def test_single_finding(self) -> None:
        findings = [
            Finding(
                file="a.py", line=10, issue="bug",
                severity=Severity.MAJOR, category="correctness", model_name="claude",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 1
        assert result[0].models == ("claude",)
        assert result[0].severity == Severity.MAJOR

    def test_proximate_findings_merged(self) -> None:
        """Findings within 5 lines in the same file should merge."""
        findings = [
            Finding(
                file="a.py", line=10, issue="bug A",
                severity=Severity.MAJOR, category="correctness", model_name="claude",
            ),
            Finding(
                file="a.py", line=13, issue="bug B",
                severity=Severity.CRITICAL, category="security", model_name="codex",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 1
        assert result[0].severity == Severity.CRITICAL  # highest wins
        assert set(result[0].models) == {"claude", "codex"}

    def test_distant_findings_separate(self) -> None:
        """Findings >5 lines apart remain separate groups."""
        findings = [
            Finding(
                file="a.py", line=10, issue="bug A",
                severity=Severity.MAJOR, category="correctness", model_name="claude",
            ),
            Finding(
                file="a.py", line=50, issue="bug B",
                severity=Severity.MINOR, category="performance", model_name="claude",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 2

    def test_different_files_separate(self) -> None:
        """Findings in different files never merge."""
        findings = [
            Finding(
                file="a.py", line=10, issue="bug",
                severity=Severity.MAJOR, category="correctness", model_name="claude",
            ),
            Finding(
                file="b.py", line=10, issue="bug",
                severity=Severity.MAJOR, category="correctness", model_name="claude",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 2

    def test_sorted_by_severity_then_agreement(self) -> None:
        """CRITICAL before MAJOR, more models before fewer."""
        findings = [
            Finding(
                file="a.py", line=10, issue="minor",
                severity=Severity.MINOR, category="perf", model_name="claude",
            ),
            Finding(
                file="b.py", line=20, issue="critical",
                severity=Severity.CRITICAL, category="security", model_name="claude",
            ),
            Finding(
                file="b.py", line=21, issue="critical too",
                severity=Severity.CRITICAL, category="security", model_name="codex",
            ),
        ]
        result = merge_findings(findings=findings)
        assert result[0].severity == Severity.CRITICAL
        assert len(result[0].models) == 2
        assert result[1].severity == Severity.MINOR

    def test_descriptions_collected(self) -> None:
        """Merged findings preserve all unique descriptions."""
        findings = [
            Finding(
                file="a.py", line=10, issue="issue A",
                severity=Severity.MAJOR, category="correctness", model_name="claude",
            ),
            Finding(
                file="a.py", line=12, issue="issue B",
                severity=Severity.MAJOR, category="correctness", model_name="codex",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 1
        assert "issue A" in result[0].descriptions
        assert "issue B" in result[0].descriptions

    def test_duplicate_descriptions_deduplicated(self) -> None:
        """Same issue text from different models kept once."""
        findings = [
            Finding(
                file="a.py", line=10, issue="same bug",
                severity=Severity.MAJOR, category="correctness", model_name="claude",
            ),
            Finding(
                file="a.py", line=10, issue="same bug",
                severity=Severity.MAJOR, category="correctness", model_name="codex",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 1
        assert result[0].descriptions == ("same bug",)
        assert result[0].issue == "same bug"

    def test_boundary_exactly_five_lines_merged(self) -> None:
        """Findings exactly 5 lines apart should merge."""
        findings = [
            Finding(
                file="a.py", line=10, issue="A",
                severity=Severity.LOW, category="style", model_name="claude",
            ),
            Finding(
                file="a.py", line=15, issue="B",
                severity=Severity.LOW, category="style", model_name="codex",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 1

    def test_boundary_six_lines_separate(self) -> None:
        """Findings 6 lines apart should be separate."""
        findings = [
            Finding(
                file="a.py", line=10, issue="A",
                severity=Severity.LOW, category="style", model_name="claude",
            ),
            Finding(
                file="a.py", line=16, issue="B",
                severity=Severity.LOW, category="style", model_name="codex",
            ),
        ]
        result = merge_findings(findings=findings)
        assert len(result) == 2
