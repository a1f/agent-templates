# Agent Templates - Design Document

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans

## Goal

A shareable repo of Claude Code skills, hooks, language rules, and templates — centered around a multi-phase agentic implementation workflow that uses parallel agents for planning, coding, reviewing, and iterative improvement.

## Architecture

The repo provides installable components for Claude Code: **skills** (agentic workflow pipeline), **rules** (conditional language-specific rules), **hooks** (Slack notifications + permission auto-approve), and **templates** (CLAUDE.md). An interactive installer lets teams pick which components to install into any project.

## Tech Stack

- Claude Code skills (SKILL.md format with YAML frontmatter)
- Claude Code conditional rules (.claude/rules/*.md with paths: frontmatter)
- Claude Code hooks (bash scripts referenced from settings.json)
- Bash installer script (interactive, menu-driven)

---

## Repo Structure

```
agent-templates/
  skills/
    implement-orchestrator/SKILL.md       # Master orchestrator
    plan-codebase/
      SKILL.md                            # Phase 1a skill
      codebase-planner-prompt.md          # Agent prompt template
    plan-tests/
      SKILL.md                            # Phase 1b skill
      test-planner-prompt.md              # Agent prompt template
    implement-parallel/
      SKILL.md                            # Phase 2 skill
      implementer-prompt.md               # Impl coder prompt
      test-coder-prompt.md                # Test coder prompt
    review-parallel/
      SKILL.md                            # Phase 3-4 skill
      refactor-reviewer-prompt.md         # Phase 3 reviewer prompts
      code-reviewer-prompt.md             # Phase 4 reviewer prompts
      consensus-rules.md                  # Voting/consensus logic
    clean-code-planner/SKILL.md           # Existing skill
    python-coding-rules/SKILL.md          # Existing skill

  rules/
    python.md
    typescript.md
    rust.md
    cpp.md

  hooks/
    notify-slack.sh
    auto-approve.sh

  templates/
    CLAUDE.md.template
    settings-hooks.json

  install.sh
  validate.sh
  README.md
```

---

## Component 1: Agentic Implementation Flow

### Overview

A multi-skill pipeline that takes an approved plan.md and executes it through 4 phases with parallel agents, culminating in a consensus-based review loop.

### Flow

```
Plan.md (approved) ──> implement-orchestrator
                           │
                    ┌──────┴──────┐
                    ▼              ▼
              Code Planner    Test Planner         Phase 1 (2 parallel)
                    │              │
                    └──────┬──────┘
                           ▼
                      impl-tmp/
                   code-spec.md + test-plan.md
                           │
                    ┌──────┴──────┐
                    ▼              ▼
              Test Coder     Impl Coder            Phase 2 (2 parallel)
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
         Architecture   DRY          Simplification  Phase 3 (3 specialized)
              ┌──┬──┬──┬──┼──┐
              ▼  ▼  ▼  ▼  ▼  ▼
           Bug  Spec Style Security Perf   Phase 4 (5 specialized CR)
                           │
                      todo.md (≥3 votes)
                           │
                    ┌──────┴──────┐
                    ▼              ▼
              Test Coder     Impl Coder     ← Loop (max 5x)
                    └──────┬──────┘
                           ▼
                     todo empty? → Done
```

### Phase 1: Planning (2 parallel agents)

**Code Planner Agent** (`plan-codebase/`)
- Input: plan.md + full codebase access
- Scans codebase for existing functions to reuse
- Lists exact files to create/modify/delete
- Writes pseudo-code or code skeleton for each change
- Applies clean-code-planner principles (DRY, SRP, dependency direction)
- Output: `impl-tmp/code-spec.md`

**Test Planner Agent** (`plan-tests/`)
- Input: plan.md + full codebase access
- Finds existing test patterns and frameworks in use
- Defines test cases per requirement from plan.md
- Specifies fixtures, mocks, test structure
- Researches testing best practices for the language
- Output: `impl-tmp/test-plan.md`

### Phase 2: Implementation (2 parallel agents)

**Impl Coder**
- Input: code-spec.md + relevant language rules
- Writes all implementation files as specified in code-spec.md
- Follows language rules from .claude/rules/
- Follows clean-code-planner skill
- Commits work when done

**Test Coder**
- Input: test-plan.md + relevant language rules
- Writes all test files as specified in test-plan.md
- Follows TDD principles
- Uses project's testing framework
- Commits work when done

No worktrees needed — test files and implementation files are naturally separate.

### Phase 3: Refactoring Review (3 specialized parallel agents)

| Reviewer | Focus |
|----------|-------|
| Architecture Reviewer | Layer violations, dependency direction, module boundaries |
| DRY Reviewer | Duplication, missed reuse opportunities, unnecessary abstractions |
| Simplification Reviewer | Over-engineering, dead code, unnecessary complexity |

Each independently reads ALL changes and produces suggestions.
Output: `impl-tmp/refactor-suggestions.md` (merged)

### Phase 4: Code Review with Consensus (5 specialized parallel agents)

| Reviewer | Focus | Flags |
|----------|-------|-------|
| Bug Hunter | Logic errors, edge cases, null handling | Bugs, crashes, data corruption |
| Spec Checker | Plan.md vs actual code | Missing features, extra features, wrong behavior |
| Style Checker | Language rules, naming, patterns | Rule violations, inconsistencies |
| Security Reviewer | OWASP top 10, input validation | Injection, auth, data exposure |
| Performance Reviewer | Complexity, memory, I/O | O(n^2) loops, leaks, unnecessary allocations |

**Consensus mechanism:**
- Each reviewer independently produces a list of issues with severity
- Issues that appear in ≥3 of 5 reviews are written to `impl-tmp/todo.md`
- Issues with <3 votes are logged but not required fixes

### Review Loop (max 5 iterations)

1. Orchestrator reads todo.md
2. If empty → Done
3. If iteration 5 → Done (report remaining issues)
4. Dispatch Test Coder + Impl Coder to fix items in todo.md
5. Re-run Phase 4 (5 code reviewers)
6. Generate new todo.md
7. Go to 1

---

## Component 2: Language Rules

Conditional rules that load when Claude reads matching file types.

### python.md
```yaml
paths:
  - "**/*.py"
  - "**/pyproject.toml"
```
Rules: type hints required, ruff for linting/formatting, pytest with fixtures, pathlib over os.path, dataclasses/pydantic for structured data, asyncio over threading, keyword-only params, no default values, modern type syntax.

### typescript.md
```yaml
paths:
  - "**/*.ts"
  - "**/*.tsx"
  - "**/package.json"
```
Rules: strict mode (no any), pnpm, vitest, const over let, zod for validation, Result types for errors, prettier + eslint.

### rust.md
```yaml
paths:
  - "**/*.rs"
  - "**/Cargo.toml"
```
Rules: cargo clippy before commit, Result<T,E> in public APIs, thiserror/anyhow, doc comments, #[must_use], iterators over loops, cargo fmt.

### cpp.md
```yaml
paths:
  - "**/*.cpp"
  - "**/*.cc"
  - "**/*.h"
  - "**/*.hpp"
  - "**/CMakeLists.txt"
```
Rules: C++17 minimum (prefer C++20), smart pointers, std::optional, clang-format, sanitizers in debug, RAII, constexpr/const.

---

## Component 3: Hooks

### notify-slack.sh

**Events:** `Notification`, `Stop`
**Behavior:**
- Reads `CLAUDE_SLACK_WEBHOOK_URL` env var
- Sends POST request with JSON payload:
  ```json
  {
    "text": "Claude Code [event]: [project] needs your attention",
    "blocks": [{"type": "section", "text": {"type": "mrkdwn", "text": "..."}}]
  }
  ```
- Includes event type, project directory, timestamp
- Silently fails if webhook URL not set (no error, just skip)

### auto-approve.sh

**Event:** `PermissionRequest`
**Behavior:**
- Reads the tool name from stdin/env
- Safe patterns (auto-approve): `get`, `list`, `read`, `search`, `query`, `view`, `fetch`, `find`, `status`, `check`, `describe`, `show`, `inspect`
- Dangerous patterns (prompt user): `delete`, `remove`, `update`, `write`, `create`, `execute`, `drop`, `kill`
- Outputs: `{"action": "allow"}` or nothing (falls through to prompt)

### settings.json integration

```json
{
  "hooks": {
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/notify-slack.sh notification"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/notify-slack.sh stop"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "$HOME/.claude/hooks/auto-approve.sh"
          }
        ]
      }
    ]
  }
}
```

---

## Component 4: Templates

### CLAUDE.md.template

A starter CLAUDE.md that:
- References the agentic workflow skills
- Documents the `/implement-orchestrator` entry point
- Lists installed language rules
- Documents context management pattern (progress.md + /clear + continue)

### settings-hooks.json

Hook configuration snippet that the installer merges into the user's existing settings.json.

---

## Component 5: Installer

### install.sh

Interactive bash script.

**Menu:**
```
Claude Code Agent Templates Installer
======================================

Target: /path/to/project

What would you like to install?

  [1] Language Rules (python, typescript, rust, cpp)
  [2] Skills (agentic workflow pipeline)
  [3] Hooks (Slack notifications, auto-approve)
  [4] CLAUDE.md template
  [5] Everything
  [0] Exit

Select options (comma-separated):
```

**Behavior per component:**

1. **Language Rules**: Copies `rules/*.md` → `<target>/.claude/rules/`. Shows diff if file exists.
2. **Skills**: Copies `skills/*/` → `~/.claude/skills/`. Skills are global (not project-specific).
3. **Hooks**: Prompts for Slack webhook URL. Copies scripts to `~/.claude/hooks/`. Merges hook config into `~/.claude/settings.json` (preserving existing settings).
4. **CLAUDE.md**: Copies template to `<target>/CLAUDE.md`. If exists, shows diff and asks to merge or replace.

**Safety:**
- Creates backup of any file before overwriting (`*.bak.TIMESTAMP`)
- Shows diff before overwriting
- Dry-run mode (`--dry-run`) to preview changes
- Uninstall mode (`--uninstall`) that removes installed components

---

## Skill Descriptions (YAML frontmatter)

These determine when Claude auto-invokes each skill:

| Skill | `description` trigger |
|-------|----------------------|
| `implement-orchestrator` | Use when the user asks to implement a plan using the agentic workflow, or invokes /implement-orchestrator |
| `plan-codebase` | Use when dispatched by implement-orchestrator to create a code specification from a plan |
| `plan-tests` | Use when dispatched by implement-orchestrator to create a test plan from a plan |
| `implement-parallel` | Use when dispatched by implement-orchestrator to execute code-spec.md and test-plan.md with parallel coders |
| `review-parallel` | Use when dispatched by implement-orchestrator to run parallel code reviews with consensus voting |

---

## Component 6: Validation & Testing

### validate.sh

A validation script that checks all components for correctness before installation or after authoring.

**Skill validation:**
- YAML frontmatter is valid (has `name` and `description` fields)
- `description` starts with "Use when"
- SKILL.md exists in each skill directory
- Referenced prompt template files (e.g., `implementer-prompt.md`) exist
- No broken cross-references between skills

**Rule validation:**
- YAML frontmatter has `paths:` field
- Each path is a valid glob pattern
- File is valid markdown after frontmatter

**Hook validation:**
- Scripts are executable (`chmod +x`)
- Scripts have valid shebang line
- For notify-slack.sh: validates webhook URL format if provided
- For auto-approve.sh: validates it outputs valid JSON
- Dry-run mode: runs hooks with mock input and checks output format

**Settings validation:**
- settings-hooks.json is valid JSON
- Hook event types are valid (`Notification`, `Stop`, `PermissionRequest`, etc.)
- Command paths reference files that exist

**Integration tests (manual):**
- `validate.sh --smoke`: Installs to a temp directory, verifies file placement
- `validate.sh --hooks`: Runs hooks with mock data, checks output
- `validate.sh --skills`: Checks all skill files parse correctly

**Usage:**
```bash
./validate.sh              # Validate all components
./validate.sh --skills     # Validate skills only
./validate.sh --rules      # Validate rules only
./validate.sh --hooks      # Validate hooks only
./validate.sh --smoke      # Full smoke test (install to temp dir)
```

---

## Success Criteria

1. User can run `./install.sh` and select components to install
2. `/implement-orchestrator` triggers the full 4-phase pipeline
3. Slack notifications fire when Claude needs input
4. Safe commands auto-approve without prompting
5. Language rules load automatically when editing matching files
6. Review consensus loop produces actionable todo.md and coders fix issues
7. The whole flow works end-to-end on a real plan.md
8. `./validate.sh` passes on all components with no errors
9. `./validate.sh --smoke` installs to temp dir and verifies file placement
