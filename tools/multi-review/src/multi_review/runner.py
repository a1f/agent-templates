"""Async model dispatch via subprocess with stdin pipe."""

import asyncio
import shlex
import subprocess
import time
from pathlib import Path

import structlog

from multi_review.config import ModelConfig
from multi_review.exceptions import ContextError, ModelRunError
from multi_review.parser import parse_findings
from multi_review.prompts.loader import assemble_prompt
from multi_review.types import ContextType, Finding, ModelResult, TaskType

logger = structlog.get_logger()


async def run_models(
    *,
    models: list[ModelConfig],
    task: TaskType,
    context_type: ContextType,
    files: list[str],
) -> list[ModelResult]:
    """Run all models in parallel and collect results."""
    code_context = gather_context(context_type=context_type, files=files)
    prompt = assemble_prompt(task=task, code_context=code_context)

    tasks = [
        _run_single_model(model=model, prompt=prompt)
        for model in models
    ]
    return list(await asyncio.gather(*tasks))


def gather_context(
    *,
    context_type: ContextType,
    files: list[str],
) -> str:
    """Build code context string based on context type."""
    if context_type == ContextType.DIFF:
        return _gather_diff()
    if context_type == ContextType.FILES:
        return _gather_files(files=files)
    if context_type == ContextType.DIRECTORY:
        return _gather_directory(directories=files)
    raise ContextError(f"Unknown context type: {context_type}")


def _gather_diff() -> str:
    """Get git diff for staged + unstaged changes."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        diff = result.stdout.strip()
        if not diff:
            # Fall back to diff of all tracked files
            result = subprocess.run(
                ["git", "diff"],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            diff = result.stdout.strip()
        if not diff:
            raise ContextError("No git diff found. Stage changes or specify files.")
        return diff
    except subprocess.CalledProcessError as exc:
        raise ContextError(f"git diff failed: {exc.stderr}") from exc
    except FileNotFoundError as exc:
        raise ContextError("git not found on PATH") from exc


def _gather_files(*, files: list[str]) -> str:
    """Read specified files and concatenate with headers."""
    if not files:
        raise ContextError("No files specified for review")

    parts: list[str] = []
    for file_path in files:
        path = Path(file_path)
        if not path.is_file():
            logger.warning("file_not_found", path=file_path)
            continue
        content = path.read_text(encoding="utf-8")
        parts.append(f"### {file_path}\n\n```\n{content}\n```")

    if not parts:
        raise ContextError("None of the specified files could be read")
    return "\n\n".join(parts)


def _gather_directory(*, directories: list[str]) -> str:
    """Read all source files in directories."""
    if not directories:
        raise ContextError("No directory specified for review")

    source_extensions = {
        ".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go",
        ".java", ".cpp", ".c", ".h", ".hpp", ".rb", ".php",
    }

    parts: list[str] = []
    for dir_path in directories:
        path = Path(dir_path)
        if not path.is_dir():
            logger.warning("directory_not_found", path=dir_path)
            continue
        for file_path in sorted(path.rglob("*")):
            if file_path.is_file() and file_path.suffix in source_extensions:
                try:
                    rel = file_path.relative_to(Path.cwd())
                except ValueError:
                    rel = file_path
                content = file_path.read_text(encoding="utf-8", errors="replace")
                parts.append(f"### {rel}\n\n```\n{content}\n```")

    if not parts:
        raise ContextError("No source files found in specified directories")
    return "\n\n".join(parts)


async def _run_single_model(
    *,
    model: ModelConfig,
    prompt: str,
) -> ModelResult:
    """Run a single model CLI via subprocess with stdin pipe."""
    log = logger.bind(model=model.name)
    log.info("model_start", command=model.command)
    start = time.monotonic()

    try:
        args = shlex.split(model.command)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            process.communicate(input=prompt.encode("utf-8")),
            timeout=model.timeout,
        )

        duration = time.monotonic() - start
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        if process.returncode != 0:
            log.error(
                "model_failed",
                returncode=process.returncode,
                stderr=stderr[:500],
                duration=duration,
            )
            return ModelResult(
                model_name=model.name,
                findings=(),
                raw_output=stdout,
                success=False,
                error=f"Exit code {process.returncode}: {stderr[:200]}",
                duration_seconds=duration,
            )

        findings = parse_findings(raw_output=stdout, model_name=model.name)
        log.info("model_complete", findings=len(findings), duration=f"{duration:.1f}s")

        return ModelResult(
            model_name=model.name,
            findings=tuple(findings),
            raw_output=stdout,
            success=True,
            duration_seconds=duration,
        )

    except TimeoutError:
        duration = time.monotonic() - start
        log.error("model_timeout", timeout=model.timeout, duration=duration)
        return ModelResult(
            model_name=model.name,
            findings=(),
            raw_output="",
            success=False,
            error=f"Timed out after {model.timeout}s",
            duration_seconds=duration,
        )
    except (OSError, ModelRunError) as exc:
        duration = time.monotonic() - start
        log.error("model_error", error=str(exc), duration=duration)
        return ModelResult(
            model_name=model.name,
            findings=(),
            raw_output="",
            success=False,
            error=str(exc),
            duration_seconds=duration,
        )
