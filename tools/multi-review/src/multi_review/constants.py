"""Defaults and constants for multi-review."""

from typing import Final

from multi_review.types import ContextType, OutputFormat, Severity, TaskType

SEVERITY_ORDER: Final[dict[Severity, int]] = {
    Severity.CRITICAL: 4,
    Severity.MAJOR: 3,
    Severity.MINOR: 2,
    Severity.LOW: 1,
}

LINE_PROXIMITY_THRESHOLD: Final[int] = 5

DEFAULT_TASK: Final[TaskType] = TaskType.CODE_REVIEW
DEFAULT_CONTEXT_TYPE: Final[ContextType] = ContextType.DIFF
DEFAULT_OUTPUT_FORMAT: Final[OutputFormat] = OutputFormat.MARKDOWN
DEFAULT_TIMEOUT: Final[int] = 120

CONFIG_FILENAMES: Final[tuple[str, ...]] = (
    "multi-review.yaml",
    "multi-review.yml",
)

CONFIG_DIR_NAME: Final[str] = "multi-review"
