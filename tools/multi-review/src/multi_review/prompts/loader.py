"""Load and assemble review prompts with code context."""

from importlib import resources

from multi_review.types import TaskType

_PROMPT_FILES: dict[TaskType, str] = {
    TaskType.BUG_HUNTING: "bug-hunting.md",
    TaskType.SECURITY_AUDIT: "security-audit.md",
    TaskType.CODE_REVIEW: "code-review.md",
    TaskType.REFACTORING: "refactoring.md",
}


def load_prompt(*, task: TaskType) -> str:
    """Load the prompt template for a given task type."""
    filename = _PROMPT_FILES[task]
    prompt_text = (
        resources.files("multi_review.prompts")
        .joinpath(filename)
        .read_text(encoding="utf-8")
    )
    return prompt_text


def assemble_prompt(*, task: TaskType, code_context: str) -> str:
    """Combine the task prompt template with code context."""
    prompt = load_prompt(task=task)
    return f"{prompt}\n\n---\n\n## Code to Review\n\n{code_context}"
