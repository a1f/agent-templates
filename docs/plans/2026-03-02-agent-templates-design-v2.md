# Agent Templates - Design Document (v2)

> For Claude: REQUIRED SUB-SKILL: Use superpowers:executing-plans
>
> **Research:** All design decisions validated against research in `docs/research/`. See individual research docs for sources and alternatives evaluated.

## Goal

A shareable repo of Claude Code skills, hooks, language rules, and templates — centered around a multi-phase agentic implementation workflow that uses parallel agents for planning, coding, reviewing, and iterative improvement.

## Architecture

The repo provides installable components for Claude Code: **skills** (agentic workflow pipeline), **rules** (conditional language-specific rules), **hooks** (Slack notifications + permission auto-approve), and **templates** (CLAUDE.md). An interactive installer lets teams pick which components to install into any project.

## Tech Stack

- Claude Code skills (SKILL.md format with YAML frontmatter) — see `docs/research/claude-code-skills.md`
- Claude Code conditional rules (.claude/rules/*.md with comma-separated paths frontmatter) — see `docs/research/claude-code-rules.md`
- Claude Code hooks (bash scripts referenced from settings.json) — see `docs/research/claude-code-hooks.md`
- Bash installer script (interactive, menu-driven, bash 3.2 compatible) — see `docs/research/installer-patterns.md`

## Research Documents

| Document | Covers |
|----------|--------|
| `claude-code-skills.md` | SKILL.md format, CSO, cross-references, token limits |
| `claude-code-rules.md` | Rules frontmatter, paths bug, loading behavior |
| `claude-code-hooks.md` | Events, stdin/stdout contract, exit codes, matchers |
| `claude-code-settings.md` | CLAUDE.md patterns, settings.json schema |
| `python-best-practices.md` | ruff, uv, mypy, typing, pytest, structlog |
| `typescript-best-practices.md` | Biome, pnpm, vitest, zod, no-enums, no-barrels |
| `rust-best-practices.md` | Edition 2024, Tokio, workspace lints, proptest |
| `cpp-best-practices.md` | C++20, clang-tidy, concepts, CMake 3.28+ |
| `agent-orchestration.md` | State passing, error recovery, coordination patterns |
| `code-review-automation.md` | Consensus mechanisms, reviewer categories, false positives |
| `slack-webhooks.md` | Block Kit, rate limits, security |
| `installer-patterns.md` | Menus, jq merge, backup/rollback, dry-run, cross-platform |
| `validation-patterns.md` | Frontmatter validation, smoke testing, ShellCheck, bats |

---

## Repo Structure

```
agent-templates/
  docs/
    research/                             # Research findings (13 docs)
    plans/                                # Design + implementation plans

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
      consensus-rules.md                  # Severity-based consensus logic
    clean-code-planner/SKILL.md           # Existing skill (packaged)
    python-coding-rules/SKILL.md          # Existing skill (packaged)

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

> Research: `docs/research/agent-orchestration.md`, `docs/research/code-review-automation.md`

### Overview

A multi-skill pipeline that takes an approved plan.md and executes it through 4 phases with parallel agents, culminating in a severity-based consensus review loop.

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
                   code-spec.md + test-plan.md + manifest.json
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
        Correct Spec Maint Security Perf  Phase 4 (5 specialized CR)
                           │
                      todo.md (severity-based consensus)
                           │
                    ┌──────┴──────┐
                    ▼              ▼
              Test Coder     Impl Coder     ← Loop (max 3x)
                    └──────┬──────┘
                           ▼
                     todo empty or <2 issues? → Done
```

### State Management

**Primary medium:** Markdown files on disk in `impl-tmp/` directory.

**JSON manifest** for orchestrator decisions:
```json
{
  "phase": 1,
  "status": "complete",
  "outputs": {
    "code_spec": "impl-tmp/code-spec.md",
    "test_plan": "impl-tmp/test-plan.md"
  },
  "timestamp": "2026-03-02T10:30:00Z"
}
```

Each subagent returns a **short summary** to the orchestrator (not the full artifact). Next-phase agents read files directly.

### Error Recovery (3-tier)

| Tier | Pattern | Handles |
|------|---------|---------|
| 1 | Per-agent retry (max 2) | Transient API failures, malformed output |
| 2 | Phase-level checkpoint + rollback | Phase failures after retries exhausted |
| 3 | Graceful degradation | One of N parallel agents fails → continue with others, retry only failed one |

Checkpoints written to `impl-tmp/checkpoint.json` before each phase.

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

### Phase 4: Code Review with Severity-Based Consensus (5 specialized parallel agents)

> Research: `docs/research/code-review-automation.md`

| Reviewer | Focus | Flags |
|----------|-------|-------|
| **Correctness** | Logic errors, edge cases, null handling, race conditions | Bugs, crashes, data corruption |
| **Spec Compliance** | Plan.md vs actual code | Missing features, extra features, wrong behavior |
| **Security** | OWASP top 10, input validation | Injection, auth, data exposure |
| **Maintainability** | Readability, DRY, complexity, testability | Over-engineering, naming, abstractions |
| **Performance** | Complexity, memory, I/O | O(n²) loops, leaks, unnecessary allocations |

**All reviewers run independently** — no visibility into each other's output. Prevents sycophancy.

**Severity-based consensus mechanism:**
```
Each reviewer outputs: [{file, line, issue, severity, category}]

CRITICAL (security, crashes, data corruption): ≥1 reviewer → todo.md
MAJOR (logic errors, spec violations):         ≥2 reviewers → todo.md
MINOR (maintainability, minor perf):           ≥3 reviewers → todo.md
LOW (style nits, suggestions):                 Logged only, not required

Issues grouped by code location (within 5 lines = same location).
Highest severity assigned to each group.
Actionability check: "Would a senior engineer change code based on this?"
```

### Review Loop (max 3 iterations)

1. Orchestrator reads todo.md
2. If empty or <2 issues → Done
3. If iteration 3 → Done (report remaining critical issues, escalate to human)
4. Dispatch Test Coder + Impl Coder to fix items in todo.md
5. Re-run Phase 4 (5 code reviewers) — **diff-only** on iterations 2-3
6. Generate new todo.md
7. Go to 1

---

## Component 2: Language Rules

> Research: `docs/research/python-best-practices.md`, `docs/research/typescript-best-practices.md`, `docs/research/rust-best-practices.md`, `docs/research/cpp-best-practices.md`
>
> **Format note:** Use comma-separated paths (not YAML arrays) due to known parsing bug. See `docs/research/claude-code-rules.md`.

### python.md
```yaml
---
paths: "**/*.py", "**/pyproject.toml"
---
```
**Target:** Python 3.12+
**Tooling:** ruff (lint/format), mypy strict (type checker), uv (packages), pytest + hypothesis
**Rules:** Type hints required, modern syntax (`list[T]`, `T | None`, `type` aliases), keyword-only params, no mutable defaults (`None` sentinel instead), Protocol over ABC, structlog for logging, `raise X from Y`, ExceptionGroup for concurrent errors, all config in pyproject.toml

### typescript.md
```yaml
---
paths: "**/*.ts", "**/*.tsx", "**/package.json"
---
```
**Target:** TypeScript 5.8+, `module: "nodenext"`
**Tooling:** Biome (preferred) or ESLint+Prettier, pnpm, vitest, Zod (Standard Schema compliant)
**Rules:** `strict: true` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` + `noPropertyAccessFromIndexSignature`, const over let, `unknown` over `any`, no enums (use `as const`), no barrel exports, Result types for errors (neverthrow or custom), Turborepo for monorepos

### rust.md
```yaml
---
paths: "**/*.rs", "**/Cargo.toml"
---
```
**Target:** Edition 2024 (Rust 1.85+)
**Tooling:** cargo fmt + cargo clippy, Tokio (async-std discontinued), thiserror + anyhow, proptest, cargo-nextest
**Rules:** `Result<T,E>` in public APIs, doc comments with `# Errors`/`# Panics`/`# Safety`, `#[must_use]`, iterators over loops, `unsafe_code = "deny"` in workspace lints, `// SAFETY:` comments mandatory, cherry-pick from pedantic (not whole group), no `println!` in library code, serde with `rename_all`/`deny_unknown_fields`

### cpp.md
```yaml
---
paths: "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp", "**/CMakeLists.txt"
---
```
**Target:** C++20 minimum, CMake 3.28+
**Tooling:** clang-format + clang-tidy, GoogleTest, vcpkg (or Conan 2)
**Rules:** Smart pointers, RAII, constexpr/const, `std::optional`, `std::format`, concepts over SFINAE, `std::span` for buffers, `std::string_view` for non-owning strings, `[[nodiscard]]`, ranges for pipelines, `-Wall -Wextra -Wpedantic -Werror` in CI, ASan+UBSan in debug. C++23 where available: `std::expected`, monadic optional, `std::print`

---

## Component 3: Hooks

> Research: `docs/research/claude-code-hooks.md`, `docs/research/slack-webhooks.md`

### notify-slack.sh

**Events:** `Notification`, `Stop`
**Behavior:**
- Reads `CLAUDE_SLACK_WEBHOOK_URL` env var
- Sends POST with simple text + Block Kit blocks:
  ```json
  {
    "text": "Claude Code [event]: [project] needs your attention",
    "blocks": [
      {
        "type": "section",
        "text": {
          "type": "mrkdwn",
          "text": "*Claude Code Stop*\n*Project:* `project`\n*Time:* timestamp"
        }
      }
    ]
  }
  ```
- 5-second curl timeout, never retry, fail silently
- Masks webhook URL in error output (show only last 6 chars)
- Silently exits if webhook URL not set

### auto-approve.sh

**Event:** `PreToolUse`
**Behavior:**
- Reads JSON from stdin, extracts `tool_name` with jq
- Safe tools (auto-approve): Read, Glob, Grep, LS, WebSearch, WebFetch
- All others: fall through to prompt (exit 0 with no output)
- Outputs: `{"hookSpecificOutput":{"permissionDecision":"allow"}}` for safe tools
- Exit code 0 always (never blocks, just allows or passes through)

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
    "PreToolUse": [
      {
        "matcher": "",
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

Hook configuration snippet that the installer deep-merges into the user's existing settings.json using `jq -s '.[0] * .[1]'`.

---

## Component 5: Installer

> Research: `docs/research/installer-patterns.md`

### install.sh

Interactive bash script. **Bash 3.2 compatible** (macOS default).

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

**CLI flags:** `--dry-run`, `--uninstall`, `--target=<path>`, `--non-interactive`

**Behavior per component:**
1. **Language Rules**: Copies `rules/*.md` → `<target>/.claude/rules/`. Shows diff if file exists.
2. **Skills**: Copies `skills/*/` → `~/.claude/skills/`. Skills are global (not project-specific).
3. **Hooks**: Prompts for Slack webhook URL. Copies scripts to `~/.claude/hooks/`. Deep-merges hook config into `~/.claude/settings.json` with `jq -s '.[0] * .[1]'`. Falls back to manual merge instructions if jq not installed.
4. **CLAUDE.md**: Copies template to `<target>/CLAUDE.md`. If exists, shows diff and asks to merge or replace.

**Safety:**
- Timestamped backups (`*.bak.TIMESTAMP`) with manifest for rollback
- Shows diff before overwriting
- Dry-run mode via wrapper functions
- Uninstall mode reads backup manifest to restore originals

---

## Component 6: Validation & Testing

> Research: `docs/research/validation-patterns.md`

### validate.sh

**ShellCheck** mandatory on all `.sh` files.

**Skill validation:**
- Pure bash: extract frontmatter with `sed`, check `name:` and `description:` fields with `grep`
- Enhanced (if yq available): structured extraction with `yq --front-matter=extract`
- `description` starts with "Use when"
- SKILL.md exists in each skill directory
- Referenced prompt template files exist
- No broken cross-references

**Rule validation:**
- YAML frontmatter has `paths:` field (comma-separated format)
- Each path is a valid glob pattern
- File is valid markdown after frontmatter

**Hook validation:**
- Scripts are executable (`chmod +x`)
- Scripts have valid shebang (`#!/usr/bin/env bash`)
- ShellCheck passes
- For notify-slack.sh: validates webhook URL format if provided
- For auto-approve.sh: validates output is valid JSON with mock input

**Settings validation:**
- settings-hooks.json is valid JSON (jq syntax check)
- Hook event types are valid (`Notification`, `Stop`, `PreToolUse`, etc.)

**Smoke tests (`validate.sh --smoke`):**
- Installs to temp directory via `--non-interactive --all`
- Verifies all expected files exist and are readable
- Verifies hooks are executable
- Verifies JSON files are valid
- Cleans up temp directory via trap

**Usage:**
```bash
./validate.sh              # Validate all components
./validate.sh --skills     # Validate skills only
./validate.sh --rules      # Validate rules only
./validate.sh --hooks      # Validate hooks + ShellCheck
./validate.sh --smoke      # Full smoke test (install to temp dir)
```

---

## Skill Descriptions (YAML frontmatter)

> Research: `docs/research/claude-code-skills.md` — CSO principles: describe triggers only, never summarize workflow.

| Skill | `description` trigger |
|-------|----------------------|
| `implement-orchestrator` | Use when the user asks to implement a plan using the agentic workflow, or invokes /implement-orchestrator |
| `plan-codebase` | Use when dispatched by implement-orchestrator to create a code specification from a plan |
| `plan-tests` | Use when dispatched by implement-orchestrator to create a test plan from a plan |
| `implement-parallel` | Use when dispatched by implement-orchestrator to execute code-spec.md and test-plan.md with parallel coders |
| `review-parallel` | Use when dispatched by implement-orchestrator to run parallel code reviews with severity-based consensus |

---

## Success Criteria

1. User can run `./install.sh` and select components to install
2. `/implement-orchestrator` triggers the full 4-phase pipeline
3. Slack notifications fire when Claude needs input
4. Safe tools auto-approve without prompting
5. Language rules load automatically when editing matching files
6. Review consensus loop produces actionable todo.md with severity-based filtering
7. The whole flow works end-to-end on a real plan.md
8. `./validate.sh` passes on all components with no errors (including ShellCheck)
9. `./validate.sh --smoke` installs to temp dir and verifies file placement
10. All research decisions are documented and traceable in `docs/research/`
