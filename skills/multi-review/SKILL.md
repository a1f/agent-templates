---
name: multi-review
description: Use when you want to run multi-model code review using external AI CLIs (claude, codex, etc.) to get diverse perspectives on code quality, bugs, security, or refactoring opportunities.
---

# Multi-Review

Run multi-model code review by dispatching prompts to multiple AI CLIs in parallel, then merging and deduplicating findings.

## When to Use

- You want diverse review perspectives from multiple AI models
- You want structured findings with severity levels and model agreement
- You want to review code for bugs, security, maintainability, or refactoring

## Prerequisites

- `multi-review` CLI installed: `cd tools/multi-review && uv pip install -e .`
- At least one AI CLI available on PATH (e.g., `claude`, `codex`)

## Usage

Run the tool via the `multi-review` CLI:

```bash
# Review git diff for bugs
multi-review run --task bug-hunting

# Security audit of specific files
multi-review run --task security-audit src/auth.py src/models.py

# Full code review of a directory
multi-review run --task code-review --context-type directory src/

# Use specific models and JSON output
multi-review run --models claude,codex --format json

# Show current config
multi-review config show

# Create default config file
multi-review config init
```

## Review Tasks

| Task | Focus |
|------|-------|
| `bug-hunting` | Logic errors, edge cases, null handling, race conditions |
| `security-audit` | Injection, auth, data exposure, input validation |
| `code-review` | Comprehensive: correctness, security, maintainability, performance |
| `refactoring` | DRY violations, complexity, coupling, dead code |

## How It Works

1. Gathers code context (git diff, specific files, or directory)
2. Loads task-specific prompt with severity definitions and JSON output format
3. Pipes prompt + code to each model CLI via stdin in parallel
4. Parses structured JSON findings from each model's output
5. Groups findings by file + line proximity (within 5 lines = same issue)
6. Merges: takes highest severity, lists all agreeing models
7. Sorts by severity DESC, then agreement count DESC
8. Outputs markdown report (with Rich terminal formatting) or JSON

## Output

Each finding shows which models flagged it:

```
- **src/auth.py:42** — [security] SQL injection via unsanitized input [claude, codex]
- **src/utils.py:100** — [performance] O(n^2) loop in data processing [claude]
```

## Configuration

Config file locations (first found wins):
1. `--config` flag
2. `./multi-review.yaml` in current directory
3. `~/.config/multi-review/config.yaml`
4. Built-in defaults

See `multi-review config show` for current effective config.
