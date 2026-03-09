"""Exception hierarchy for multi-review."""


class MultiReviewError(Exception):
    """Base exception for all multi-review errors."""


class ConfigError(MultiReviewError):
    """Invalid or missing configuration."""


class ModelRunError(MultiReviewError):
    """A model subprocess failed."""


class ParseError(MultiReviewError):
    """Failed to parse model output as structured findings."""


class ContextError(MultiReviewError):
    """Failed to gather code context (diff, files, directory)."""
