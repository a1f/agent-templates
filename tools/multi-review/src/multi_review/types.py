"""Domain types for multi-review."""

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    """Review finding severity level."""

    CRITICAL = "CRITICAL"
    MAJOR = "MAJOR"
    MINOR = "MINOR"
    LOW = "LOW"


class TaskType(StrEnum):
    """Available review task types."""

    BUG_HUNTING = "bug-hunting"
    SECURITY_AUDIT = "security-audit"
    CODE_REVIEW = "code-review"
    REFACTORING = "refactoring"


class ContextType(StrEnum):
    """How code context is gathered for review."""

    DIFF = "diff"
    FILES = "files"
    DIRECTORY = "directory"


class OutputFormat(StrEnum):
    """Report output format."""

    MARKDOWN = "markdown"
    JSON = "json"


@dataclass(frozen=True)
class Finding:
    """Single finding from one model."""

    file: str
    line: int
    issue: str
    severity: Severity
    category: str
    model_name: str


@dataclass(frozen=True)
class ModelResult:
    """Aggregated result from a single model run."""

    model_name: str
    findings: tuple[Finding, ...]
    raw_output: str
    success: bool
    error: str | None = None
    duration_seconds: float = 0.0


@dataclass(frozen=True)
class MergedFinding:
    """Finding after merge/dedup across models."""

    file: str
    line: int
    issue: str
    severity: Severity
    category: str
    models: tuple[str, ...]
    descriptions: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReviewReport:
    """Final review report with all merged findings."""

    task: TaskType
    findings: tuple[MergedFinding, ...]
    model_results: tuple[ModelResult, ...]
    context_type: ContextType
    files_reviewed: tuple[str, ...] = field(default_factory=tuple)
