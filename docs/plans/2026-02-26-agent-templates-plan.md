# Agent Templates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shareable repo of Claude Code skills, hooks, rules, and an installer — centered around a multi-phase agentic implementation workflow.

**Architecture:** Flat-by-type repo structure (`skills/`, `rules/`, `hooks/`, `templates/`). Skills follow the superpowers SKILL.md format. Installer is an interactive bash script that copies components to target locations. Validate script checks all artifacts for correctness.

**Tech Stack:** Bash, Claude Code SKILL.md format (YAML frontmatter + markdown), JSON (settings/hooks config)

---

## Task 1: Create directory structure

**Files:**
- Create: `skills/`, `rules/`, `hooks/`, `templates/`

**Step 1: Create all directories**

```bash
mkdir -p skills/implement-orchestrator
mkdir -p skills/plan-codebase
mkdir -p skills/plan-tests
mkdir -p skills/implement-parallel
mkdir -p skills/review-parallel
mkdir -p skills/clean-code-planner
mkdir -p skills/python-coding-rules
mkdir -p rules
mkdir -p hooks
mkdir -p templates
```

**Step 2: Verify structure**

Run: `find . -type d -not -path './.git/*' | sort`
Expected: all directories listed

**Step 3: Commit**

```bash
git add -A && git commit -m "chore: create directory structure for agent-templates"
```

---

## Task 2: Language rules — Python

**Files:**
- Create: `rules/python.md`

**Step 1: Write the rule file**

Write `rules/python.md` with the full Python rules content. This is a conditional rule that loads when Claude reads Python files. Include:
- YAML frontmatter with `paths:` matching `**/*.py` and `**/pyproject.toml`
- All rules from the existing `python-coding-rules` skill PLUS the standard rules from the design doc
- Rules: type hints on all functions/params/returns, ruff for linting/formatting, pytest with fixtures in conftest.py, pathlib.Path over os.path, dataclasses/pydantic for structured data, asyncio over threading, keyword-only params (`*` first), no default parameter values, modern type syntax (`list[T]` not `List[T]`, `T | None` not `Optional[T]`), Final[T] for constants, empty `__init__.py`, frozen dataclass for multi-value returns

**Step 2: Verify frontmatter**

Run: `head -5 rules/python.md`
Expected: YAML frontmatter with `---`, `paths:`, glob patterns, closing `---`

**Step 3: Commit**

```bash
git add rules/python.md && git commit -m "feat: add Python conditional language rules"
```

---

## Task 3: Language rules — TypeScript

**Files:**
- Create: `rules/typescript.md`

**Step 1: Write the rule file**

Write `rules/typescript.md`. Include:
- YAML frontmatter with `paths:` matching `**/*.ts`, `**/*.tsx`, `**/package.json`
- Rules: strict mode (no `any` unless absolutely necessary), pnpm as package manager, vitest for testing, prefer `const` over `let` (never `var`), zod for runtime validation, Result types or typed errors (not bare try/catch), run `prettier --write` and `eslint --fix` after changes, prefer named exports, use `satisfies` for type narrowing, prefer `unknown` over `any` in catch blocks

**Step 2: Commit**

```bash
git add rules/typescript.md && git commit -m "feat: add TypeScript conditional language rules"
```

---

## Task 4: Language rules — Rust

**Files:**
- Create: `rules/rust.md`

**Step 1: Write the rule file**

Write `rules/rust.md`. Include:
- YAML frontmatter with `paths:` matching `**/*.rs`, `**/Cargo.toml`
- Rules: run `cargo clippy --all-targets` before committing, `Result<T, E>` in all public APIs (never `unwrap()` in production), prefer `thiserror` for library errors and `anyhow` for application errors, all public functions require `///` doc comments, use `#[must_use]` on functions returning values that shouldn't be ignored, prefer iterators over explicit loops, run `cargo fmt` after any changes, use `derive` macros where possible, prefer `&str` over `String` in function parameters

**Step 2: Commit**

```bash
git add rules/rust.md && git commit -m "feat: add Rust conditional language rules"
```

---

## Task 5: Language rules — C++

**Files:**
- Create: `rules/cpp.md`

**Step 1: Write the rule file**

Write `rules/cpp.md`. Include:
- YAML frontmatter with `paths:` matching `**/*.cpp`, `**/*.cc`, `**/*.h`, `**/*.hpp`, `**/CMakeLists.txt`
- Rules: use modern C++ (C++17 minimum, prefer C++20), smart pointers over raw pointers (`unique_ptr`, `shared_ptr`), use `std::optional` for nullable values, run `clang-format` after changes, enable sanitizers in debug builds (`-fsanitize=address,undefined`), RAII for resource management, use `constexpr` and `const` aggressively, prefer `std::string_view` over `const std::string&` for non-owning references, use structured bindings, prefer `std::variant` over `union`

**Step 2: Commit**

```bash
git add rules/cpp.md && git commit -m "feat: add C++ conditional language rules"
```

---

## Task 6: Copy existing skills

**Files:**
- Create: `skills/clean-code-planner/SKILL.md`
- Create: `skills/python-coding-rules/SKILL.md`

**Step 1: Copy existing skill files**

Copy from `~/.claude/skills/clean-code-planner/SKILL.md` to `skills/clean-code-planner/SKILL.md`.
Copy from `~/.claude/skills/python-coding-rules/SKILL.md` to `skills/python-coding-rules/SKILL.md`.

These are exact copies — no modifications needed.

**Step 2: Verify**

Run: `head -3 skills/clean-code-planner/SKILL.md && head -3 skills/python-coding-rules/SKILL.md`
Expected: Both show YAML frontmatter starting with `---`

**Step 3: Commit**

```bash
git add skills/clean-code-planner/ skills/python-coding-rules/ && git commit -m "feat: add existing clean-code-planner and python-coding-rules skills"
```

---

## Task 7: Hooks — Slack notification

**Files:**
- Create: `hooks/notify-slack.sh`

**Step 1: Write the hook script**

Write `hooks/notify-slack.sh`:

```bash
#!/usr/bin/env bash
# Claude Code hook: Send Slack notification when Claude needs input or finishes.
# Events: Notification, Stop
# Requires: CLAUDE_SLACK_WEBHOOK_URL environment variable
#
# Usage in settings.json hooks:
#   "command": "/path/to/notify-slack.sh notification"
#   "command": "/path/to/notify-slack.sh stop"

set -euo pipefail

EVENT_TYPE="${1:-unknown}"
WEBHOOK_URL="${CLAUDE_SLACK_WEBHOOK_URL:-}"

# Silently exit if no webhook configured
if [[ -z "$WEBHOOK_URL" ]]; then
    exit 0
fi

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
PROJECT_NAME=$(basename "$PROJECT_DIR")
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

case "$EVENT_TYPE" in
    notification)
        EMOJI=":bell:"
        MESSAGE="Claude Code needs your input"
        COLOR="#ff9900"
        ;;
    stop)
        EMOJI=":white_check_mark:"
        MESSAGE="Claude Code finished working"
        COLOR="#36a64f"
        ;;
    *)
        EMOJI=":robot_face:"
        MESSAGE="Claude Code event: $EVENT_TYPE"
        COLOR="#439FE0"
        ;;
esac

PAYLOAD=$(cat <<JSONEOF
{
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "${EMOJI} *${MESSAGE}*\n*Project:* ${PROJECT_NAME}\n*Time:* ${TIMESTAMP}"
            }
        }
    ]
}
JSONEOF
)

curl -s -X POST -H 'Content-type: application/json' \
    --data "$PAYLOAD" \
    "$WEBHOOK_URL" > /dev/null 2>&1 || true

exit 0
```

**Step 2: Make executable**

Run: `chmod +x hooks/notify-slack.sh`

**Step 3: Verify shebang and permissions**

Run: `head -1 hooks/notify-slack.sh && ls -la hooks/notify-slack.sh`
Expected: `#!/usr/bin/env bash` and `-rwxr-xr-x` permissions

**Step 4: Commit**

```bash
git add hooks/notify-slack.sh && git commit -m "feat: add Slack notification hook script"
```

---

## Task 8: Hooks — Auto-approve permissions

**Files:**
- Create: `hooks/auto-approve.sh`

**Step 1: Write the hook script**

Write `hooks/auto-approve.sh`:

```bash
#!/usr/bin/env bash
# Claude Code hook: Auto-approve safe read-only permission requests.
# Event: PermissionRequest
# Reads tool info from stdin JSON, outputs decision JSON.
#
# Safe (auto-approve): get, list, read, search, query, view, fetch, find, status, check, describe, show, inspect
# Dangerous (prompt user): delete, remove, update, write, create, execute, drop, kill

set -euo pipefail

# Read the permission request from stdin
INPUT=$(cat)

# Extract the tool name (handles both "tool" and "tool_name" fields)
TOOL_NAME=$(echo "$INPUT" | grep -oE '"(tool|tool_name)"\s*:\s*"[^"]*"' | head -1 | grep -oE '"[^"]*"$' | tr -d '"' | tr '[:upper:]' '[:lower:]')

# If we can't parse the tool name, fall through to prompt
if [[ -z "$TOOL_NAME" ]]; then
    exit 0
fi

# Safe patterns — auto-approve
SAFE_PATTERNS="get list read search query view fetch find status check describe show inspect retrieve analyze health stats"

for pattern in $SAFE_PATTERNS; do
    if [[ "$TOOL_NAME" == *"$pattern"* ]]; then
        echo '{"action": "allow"}'
        exit 0
    fi
done

# Everything else falls through to the default prompt
exit 0
```

**Step 2: Make executable**

Run: `chmod +x hooks/auto-approve.sh`

**Step 3: Verify**

Run: `echo '{"tool": "read_file"}' | hooks/auto-approve.sh`
Expected: `{"action": "allow"}`

Run: `echo '{"tool": "delete_branch"}' | hooks/auto-approve.sh`
Expected: no output (falls through to prompt)

**Step 4: Commit**

```bash
git add hooks/auto-approve.sh && git commit -m "feat: add permission auto-approve hook script"
```

---

## Task 9: Templates — settings-hooks.json

**Files:**
- Create: `templates/settings-hooks.json`

**Step 1: Write the hook configuration template**

Write `templates/settings-hooks.json` — a JSON snippet that the installer merges into `~/.claude/settings.json`:

```json
{
    "hooks": {
        "Notification": [
            {
                "matcher": "",
                "hooks": [
                    {
                        "type": "command",
                        "command": "~/.claude/hooks/notify-slack.sh notification"
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
                        "command": "~/.claude/hooks/notify-slack.sh stop"
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
                        "command": "~/.claude/hooks/auto-approve.sh"
                    }
                ]
            }
        ]
    }
}
```

**Step 2: Validate JSON**

Run: `python3 -c "import json; json.load(open('templates/settings-hooks.json'))"`
Expected: no output (valid JSON)

**Step 3: Commit**

```bash
git add templates/settings-hooks.json && git commit -m "feat: add hook configuration template"
```

---

## Task 10: Templates — CLAUDE.md.template

**Files:**
- Create: `templates/CLAUDE.md.template`

**Step 1: Write the CLAUDE.md template**

Write `templates/CLAUDE.md.template` — a starter CLAUDE.md that projects can adopt. Contents:

```markdown
# Project Guidelines

## Agentic Implementation Workflow

When implementing plans, use the multi-phase agentic workflow:

1. Run `/implement-orchestrator` with a plan.md file
2. The orchestrator dispatches parallel agents for planning, coding, reviewing
3. Reviews use consensus voting (≥3/5 reviewers must flag an issue for it to be mandatory)
4. Coders fix flagged issues in a loop (max 5 iterations)

## Language Rules

Language-specific rules are loaded automatically from `.claude/rules/` when editing matching files:
- Python: `.claude/rules/python.md`
- TypeScript: `.claude/rules/typescript.md`
- Rust: `.claude/rules/rust.md`
- C++: `.claude/rules/cpp.md`

## Context Management

For long sessions that approach context limits:
1. Write current progress to `progress.md` with: what's done, what's next, any blockers
2. Run `/clear` to reset context
3. Start new message: "Read progress.md and continue"

## Hooks

- **Slack notifications**: Claude sends Slack messages when it needs input or finishes
- **Auto-approve**: Read-only operations are auto-approved; destructive operations prompt for confirmation
```

**Step 2: Commit**

```bash
git add templates/CLAUDE.md.template && git commit -m "feat: add CLAUDE.md template"
```

---

## Task 11: Skill — implement-orchestrator

**Files:**
- Create: `skills/implement-orchestrator/SKILL.md`

**Step 1: Write the orchestrator skill**

This is the master skill that drives the entire agentic workflow. Write `skills/implement-orchestrator/SKILL.md`:

```markdown
---
name: implement-orchestrator
description: Use when the user asks to implement a plan using the agentic workflow, or invokes /implement-orchestrator
---

# Implement Orchestrator

Execute an approved plan through 4 phases of parallel agents: planning, coding, reviewing, and iterative improvement.

## When to Use

- User says "implement this plan" or "execute plan.md"
- User invokes `/implement-orchestrator`
- An approved plan.md exists and is ready for implementation

## Prerequisites

- An approved plan file (plan.md or docs/plans/*.md)
- The plan must be reviewed and agreed upon before starting

## The Process

### Phase 1: Planning (2 parallel agents)

Create `impl-tmp/` directory in the project root.

Dispatch two agents in parallel using the Task tool:

**Agent 1 — Code Planner:**
- subagent_type: general-purpose
- Prompt: Use the template from `plan-codebase/codebase-planner-prompt.md`
- Provide the FULL TEXT of plan.md in the prompt (do not make the agent read the file)
- Output: Agent writes `impl-tmp/code-spec.md`

**Agent 2 — Test Planner:**
- subagent_type: general-purpose
- Prompt: Use the template from `plan-tests/test-planner-prompt.md`
- Provide the FULL TEXT of plan.md in the prompt (do not make the agent read the file)
- Output: Agent writes `impl-tmp/test-plan.md`

Wait for both agents to complete. Read and verify both output files exist.

### Phase 2: Implementation (2 parallel agents)

Dispatch two agents in parallel:

**Agent 1 — Impl Coder:**
- subagent_type: general-purpose
- Prompt: Use the template from `implement-parallel/implementer-prompt.md`
- Provide FULL TEXT of `impl-tmp/code-spec.md`
- Provide relevant language rules from `.claude/rules/`
- Agent writes implementation files and commits

**Agent 2 — Test Coder:**
- subagent_type: general-purpose
- Prompt: Use the template from `implement-parallel/test-coder-prompt.md`
- Provide FULL TEXT of `impl-tmp/test-plan.md`
- Provide relevant language rules from `.claude/rules/`
- Agent writes test files and commits

Wait for both agents. Run the test suite to verify baseline.

### Phase 3: Refactoring Review (3 parallel agents)

Dispatch three specialized reviewers in parallel using the template from `review-parallel/refactor-reviewer-prompt.md`:

1. **Architecture Reviewer** — focus: layer violations, dependency direction, module boundaries
2. **DRY Reviewer** — focus: duplication, missed reuse, unnecessary abstractions
3. **Simplification Reviewer** — focus: over-engineering, dead code, unnecessary complexity

Each reviewer reads all changes (use `git diff` from before Phase 2).
Merge their suggestions into `impl-tmp/refactor-suggestions.md`.

Present refactoring suggestions to the user. Apply approved suggestions.

### Phase 4: Code Review with Consensus (5 parallel agents)

Dispatch five specialized reviewers in parallel using the template from `review-parallel/code-reviewer-prompt.md`:

1. **Bug Hunter** — logic errors, edge cases, null/error handling
2. **Spec Checker** — plan.md requirements vs actual implementation
3. **Style Checker** — language rules compliance, naming, patterns
4. **Security Reviewer** — OWASP top 10, input validation, auth
5. **Performance Reviewer** — complexity, memory, I/O efficiency

Each reviewer independently produces a JSON list of issues:
```json
[{"id": "issue-1", "severity": "critical|important|minor", "file": "path", "line": N, "description": "..."}]
```

**Consensus:** Count how many reviewers flagged each issue (match by file+description similarity).
Issues with ≥3 votes → write to `impl-tmp/todo.md` as mandatory fixes.
Issues with <3 votes → log to `impl-tmp/review-notes.md` (informational only).

### Review Loop (max 5 iterations)

```
iteration = 0
while todo.md is not empty AND iteration < 5:
    iteration += 1
    Dispatch Test Coder + Impl Coder to fix todo.md items
    Re-run Phase 4 (5 code reviewers)
    Regenerate todo.md from consensus
```

When loop exits:
- If todo.md is empty: "All issues resolved. Implementation complete."
- If iteration limit hit: "Reached max iterations. Remaining issues in impl-tmp/todo.md."

### Completion

1. Run full test suite
2. Report summary: files created/modified, test results, review iterations completed
3. Clean up `impl-tmp/` (or keep if user wants to inspect)

## Red Flags

- Never start without an approved plan
- Never skip any phase
- Never dispatch Phase 2 before Phase 1 outputs are verified
- Never skip the consensus mechanism — all 5 reviewers must run
- Never exceed 5 review loop iterations
- Always provide FULL TEXT of plans/specs to agents (never make agents read files)
```

**Step 2: Verify frontmatter**

Run: `head -4 skills/implement-orchestrator/SKILL.md`
Expected: `---`, `name:`, `description:`, `---`

**Step 3: Commit**

```bash
git add skills/implement-orchestrator/SKILL.md && git commit -m "feat: add implement-orchestrator master skill"
```

---

## Task 12: Skill — plan-codebase

**Files:**
- Create: `skills/plan-codebase/SKILL.md`
- Create: `skills/plan-codebase/codebase-planner-prompt.md`

**Step 1: Write the skill file**

Write `skills/plan-codebase/SKILL.md`:

```markdown
---
name: plan-codebase
description: Use when dispatched by implement-orchestrator to create a code specification from a plan
---

# Plan Codebase

Scan the codebase and produce a detailed code specification from an implementation plan.

## When to Use

- Dispatched by `implement-orchestrator` during Phase 1
- Not invoked directly by users

## Output

Write `impl-tmp/code-spec.md` containing:
- List of files to create, modify, or delete
- For each file: exact path, purpose, pseudo-code or code skeleton
- Existing functions/modules to reuse (with file paths)
- Dependency direction between new and existing modules
- Architecture layer assignment for new components

## Process

1. Read the plan provided in your prompt
2. Scan the codebase: find existing patterns, modules, utilities
3. Identify reuse opportunities (grep for similar functionality)
4. Plan exact file changes with pseudo-code
5. Apply clean-code-planner principles (DRY, SRP, dependency direction)
6. Write output to `impl-tmp/code-spec.md`
```

**Step 2: Write the agent prompt template**

Write `skills/plan-codebase/codebase-planner-prompt.md`:

```markdown
# Codebase Planner Agent Prompt Template

Use with Task tool (subagent_type: general-purpose):

```
description: "Plan codebase changes for: [feature name]"
prompt: |
    You are a code planner. Your job is to analyze the codebase and produce
    a detailed code specification for implementing a plan.

    ## The Plan

    [PASTE FULL TEXT OF plan.md HERE]

    ## Your Job

    1. Scan the codebase thoroughly:
       - Use Glob to find relevant files by pattern
       - Use Grep to search for related functionality
       - Read key files to understand existing patterns

    2. Identify reuse opportunities:
       - Existing utilities, helpers, base classes
       - Existing patterns (how are similar features structured?)
       - Existing test patterns

    3. Plan the changes:
       - List every file to create, modify, or delete
       - For each file: exact path, what changes, pseudo-code
       - Note dependencies between files

    4. Apply clean code principles:
       - Single Responsibility: one reason to change per module
       - DRY: reuse existing code, don't duplicate
       - Dependency direction: stable ← volatile

    5. Write your output to `impl-tmp/code-spec.md` using this format:

    ```markdown
    # Code Specification: [feature name]

    ## Files to Create
    - `path/to/file.ext` — Purpose: [description]
      ```[lang]
      // pseudo-code or skeleton
      ```

    ## Files to Modify
    - `path/to/existing.ext` — Change: [description]
      Lines affected: [range]
      ```[lang]
      // new/modified code
      ```

    ## Files to Delete
    - `path/to/obsolete.ext` — Reason: [why]

    ## Reuse Opportunities
    - `existing/util.ext:function_name()` — use for [purpose]

    ## Dependency Map
    - new_module → existing_module (direction: correct)
    ```

    ## Constraints
    - Do NOT write implementation code — only specs and pseudo-code
    - Do NOT modify any existing files
    - Do NOT create the implementation files
    - ONLY create `impl-tmp/code-spec.md`
```
```

**Step 3: Commit**

```bash
git add skills/plan-codebase/ && git commit -m "feat: add plan-codebase skill with agent prompt template"
```

---

## Task 13: Skill — plan-tests

**Files:**
- Create: `skills/plan-tests/SKILL.md`
- Create: `skills/plan-tests/test-planner-prompt.md`

**Step 1: Write the skill file**

Write `skills/plan-tests/SKILL.md`:

```markdown
---
name: plan-tests
description: Use when dispatched by implement-orchestrator to create a test plan from a plan
---

# Plan Tests

Analyze the codebase and plan to produce a comprehensive test plan from an implementation plan.

## When to Use

- Dispatched by `implement-orchestrator` during Phase 1
- Not invoked directly by users

## Output

Write `impl-tmp/test-plan.md` containing:
- Test framework and configuration to use (detected from existing codebase)
- Test file paths (matching project conventions)
- Test cases per requirement from the plan
- Fixtures, mocks, and test data needed
- Integration vs unit test split
- Expected test commands and outputs

## Process

1. Read the plan provided in your prompt
2. Scan existing tests: find framework, patterns, fixtures, conftest
3. Research testing best practices for the language
4. Define test cases per plan requirement
5. Write output to `impl-tmp/test-plan.md`
```

**Step 2: Write the agent prompt template**

Write `skills/plan-tests/test-planner-prompt.md`:

```markdown
# Test Planner Agent Prompt Template

Use with Task tool (subagent_type: general-purpose):

```
description: "Plan tests for: [feature name]"
prompt: |
    You are a test planner. Your job is to analyze the codebase and produce
    a comprehensive test plan for implementing a plan.

    ## The Plan

    [PASTE FULL TEXT OF plan.md HERE]

    ## Your Job

    1. Analyze existing test infrastructure:
       - Use Glob to find test files (test_*.py, *.test.ts, *_test.rs, etc.)
       - Read a few test files to understand patterns
       - Find conftest.py / test helpers / fixtures
       - Identify test framework (pytest, vitest, cargo test, gtest, etc.)

    2. Extract testable requirements from the plan:
       - Each requirement → one or more test cases
       - Happy path + edge cases + error cases
       - Integration tests for cross-module interactions

    3. Design test structure:
       - Test file paths following project conventions
       - Test function names describing behavior
       - Fixtures and mocks needed
       - Test data / factories

    4. Write your output to `impl-tmp/test-plan.md` using this format:

    ```markdown
    # Test Plan: [feature name]

    ## Test Infrastructure
    - Framework: [pytest/vitest/cargo test/etc.]
    - Config: [existing config file path]
    - Run command: [exact command to run tests]

    ## Test Files to Create
    ### `tests/path/to/test_file.ext`

    **test_behavior_description:**
    - Setup: [what fixtures/mocks needed]
    - Action: [what to call]
    - Assert: [expected outcome]

    **test_edge_case:**
    - Setup: ...
    - Action: ...
    - Assert: ...

    ## Fixtures Needed
    - `fixture_name` — provides [what], defined in [where]

    ## Mocks Needed
    - `mock_name` — mocks [what], returns [what]
    ```

    ## Constraints
    - Do NOT write test code — only the plan
    - Do NOT create test files
    - ONLY create `impl-tmp/test-plan.md`
    - Focus on BEHAVIOR testing, not implementation details
    - Every test should test one thing
```
```

**Step 3: Commit**

```bash
git add skills/plan-tests/ && git commit -m "feat: add plan-tests skill with agent prompt template"
```

---

## Task 14: Skill — implement-parallel

**Files:**
- Create: `skills/implement-parallel/SKILL.md`
- Create: `skills/implement-parallel/implementer-prompt.md`
- Create: `skills/implement-parallel/test-coder-prompt.md`

**Step 1: Write the skill file**

Write `skills/implement-parallel/SKILL.md`:

```markdown
---
name: implement-parallel
description: Use when dispatched by implement-orchestrator to execute code-spec.md and test-plan.md with parallel coders
---

# Implement Parallel

Dispatch two parallel coders: one writes implementation code, one writes tests.

## When to Use

- Dispatched by `implement-orchestrator` during Phase 2
- After Phase 1 has produced `impl-tmp/code-spec.md` and `impl-tmp/test-plan.md`

## Agents

| Agent | Input | Output | Prompt Template |
|-------|-------|--------|----------------|
| Impl Coder | code-spec.md + language rules | Implementation files | `implementer-prompt.md` |
| Test Coder | test-plan.md + language rules | Test files | `test-coder-prompt.md` |

## Process

1. Read `impl-tmp/code-spec.md` and `impl-tmp/test-plan.md`
2. Detect language from file extensions in the specs
3. Read relevant language rules from `.claude/rules/`
4. Dispatch both agents in parallel using Task tool
5. Wait for both to complete
6. Run the test suite to verify baseline

## Conflict Prevention

- Impl Coder ONLY touches implementation files (src/, lib/, etc.)
- Test Coder ONLY touches test files (tests/, __tests__/, etc.)
- Neither touches config files, docs, or each other's files
```

**Step 2: Write the implementer prompt template**

Write `skills/implement-parallel/implementer-prompt.md`:

```markdown
# Implementer Agent Prompt Template

Use with Task tool (subagent_type: general-purpose):

```
description: "Implement code changes for: [feature name]"
prompt: |
    You are an implementation coder. Your job is to write production code
    following a detailed code specification.

    ## Code Specification

    [PASTE FULL TEXT OF impl-tmp/code-spec.md HERE]

    ## Language Rules

    [PASTE RELEVANT LANGUAGE RULES FROM .claude/rules/ HERE]

    ## Your Job

    1. Read the code specification carefully
    2. For each file to create: write the complete file
    3. For each file to modify: make the specified changes
    4. For each file to delete: remove it
    5. Follow the language rules strictly
    6. Follow clean code principles:
       - DRY: Don't repeat yourself
       - SRP: Single responsibility per function/module
       - Clear naming that reveals intent
       - No over-engineering — minimum code for the spec
    7. Commit your work when done

    ## Before Reporting Back: Self-Review

    - Did I implement everything in the spec?
    - Does the code follow language rules?
    - Are names clear and accurate?
    - Did I avoid over-building (YAGNI)?
    - Did I reuse existing code as noted in the spec?

    Fix any issues found during self-review before reporting.

    ## Report Format

    - Files created (with paths)
    - Files modified (with paths and summary of changes)
    - Files deleted
    - Self-review findings (if any)
    - Any concerns or questions

    ## Constraints

    - ONLY touch implementation files — never test files
    - Follow the spec exactly — no extra features
    - Commit all changes with a descriptive message
```
```

**Step 3: Write the test coder prompt template**

Write `skills/implement-parallel/test-coder-prompt.md`:

```markdown
# Test Coder Agent Prompt Template

Use with Task tool (subagent_type: general-purpose):

```
description: "Write tests for: [feature name]"
prompt: |
    You are a test coder. Your job is to write comprehensive tests
    following a detailed test plan.

    ## Test Plan

    [PASTE FULL TEXT OF impl-tmp/test-plan.md HERE]

    ## Language Rules

    [PASTE RELEVANT LANGUAGE RULES FROM .claude/rules/ HERE]

    ## Your Job

    1. Read the test plan carefully
    2. Set up test infrastructure (fixtures, mocks, helpers) as specified
    3. Write each test case from the plan
    4. Each test should:
       - Have a descriptive name explaining the behavior tested
       - Follow Arrange-Act-Assert pattern
       - Test ONE thing
       - Be independent (no test depends on another)
    5. Follow the language rules for testing
    6. Commit your work when done

    ## Test Quality Checklist

    - Tests describe behavior, not implementation
    - Edge cases are covered (empty, null, boundary values)
    - Error cases are covered (invalid input, failures)
    - Tests are readable without comments
    - Mocks are minimal — only mock external dependencies
    - No test logic (no if/else in tests)

    ## Report Format

    - Test files created (with paths)
    - Number of test cases written
    - Test run command and results (run the tests!)
    - Any test plan items that couldn't be implemented (and why)

    ## Constraints

    - ONLY touch test files — never implementation files
    - Follow the test plan exactly
    - Run the tests before reporting (they may fail if implementation isn't done yet — that's expected)
    - Commit all changes with a descriptive message
```
```

**Step 4: Commit**

```bash
git add skills/implement-parallel/ && git commit -m "feat: add implement-parallel skill with coder prompt templates"
```

---

## Task 15: Skill — review-parallel

**Files:**
- Create: `skills/review-parallel/SKILL.md`
- Create: `skills/review-parallel/refactor-reviewer-prompt.md`
- Create: `skills/review-parallel/code-reviewer-prompt.md`
- Create: `skills/review-parallel/consensus-rules.md`

**Step 1: Write the skill file**

Write `skills/review-parallel/SKILL.md`:

```markdown
---
name: review-parallel
description: Use when dispatched by implement-orchestrator to run parallel code reviews with consensus voting
---

# Review Parallel

Run parallel specialized reviewers with consensus-based issue resolution.

## When to Use

- Dispatched by `implement-orchestrator` during Phase 3 and Phase 4
- After implementation code and tests are written

## Phase 3: Refactoring Review (3 agents)

Dispatch three specialized reviewers in parallel. Each reads ALL changes via `git diff`.

| Reviewer | Focus | Prompt Context |
|----------|-------|---------------|
| Architecture | Layer violations, dependency direction, module boundaries | "You are an architecture reviewer..." |
| DRY | Duplication, missed reuse, unnecessary abstractions | "You are a DRY reviewer..." |
| Simplification | Over-engineering, dead code, complexity | "You are a simplification reviewer..." |

Each reviewer outputs suggestions to their section of `impl-tmp/refactor-suggestions.md`.
Present suggestions to user. Apply approved ones.

## Phase 4: Code Review with Consensus (5 agents)

Dispatch five specialized reviewers in parallel. Each independently reviews all changes.

| Reviewer | Focus |
|----------|-------|
| Bug Hunter | Logic errors, edge cases, null/error handling |
| Spec Checker | Plan requirements vs actual implementation |
| Style Checker | Language rules, naming, patterns |
| Security | OWASP top 10, input validation, auth |
| Performance | Complexity, memory, I/O efficiency |

### Consensus Mechanism

See `consensus-rules.md` for the full algorithm.

Summary: Each reviewer outputs issues as JSON. The orchestrator counts votes per issue
(matching by file + description similarity). Issues with ≥3 votes → `impl-tmp/todo.md`.

## Output Format

Each reviewer MUST output issues as a JSON array:
```json
[
    {
        "id": "unique-id",
        "severity": "critical|important|minor",
        "file": "path/to/file.ext",
        "line": 42,
        "description": "Clear description of the issue",
        "suggestion": "How to fix it"
    }
]
```
```

**Step 2: Write the refactor reviewer prompt template**

Write `skills/review-parallel/refactor-reviewer-prompt.md`:

```markdown
# Refactoring Reviewer Agent Prompt Template

Use with Task tool (subagent_type: general-purpose):

```
description: "Review for [architecture|DRY|simplification]: [feature name]"
prompt: |
    You are a [ROLE] reviewer. Your job is to review code changes
    and suggest improvements in your area of expertise.

    ## Your Specialization: [ROLE]

    [For Architecture Reviewer:]
    Focus on: layer violations, dependency direction (stable ← volatile),
    module boundaries, separation of concerns, interface design.

    [For DRY Reviewer:]
    Focus on: code duplication, missed reuse opportunities, unnecessary
    abstractions, copy-paste patterns, knowledge that lives in two places.

    [For Simplification Reviewer:]
    Focus on: over-engineering, dead code, unnecessary complexity, premature
    abstraction, features beyond requirements, code that can be deleted.

    ## Changes to Review

    [PASTE GIT DIFF HERE or provide commit range]

    ## Original Plan

    [PASTE PLAN SUMMARY for context]

    ## Your Job

    1. Read ALL changes carefully
    2. Identify issues in your specialization area ONLY
    3. For each issue, provide:
       - File and line reference
       - What's wrong
       - How to fix it
       - Severity (critical / important / minor)
    4. Be specific — vague suggestions are useless

    ## Output Format

    Write your findings as a markdown section:

    ```markdown
    ## [Role] Review

    ### Issue 1: [title]
    - **File:** `path/to/file:line`
    - **Severity:** critical|important|minor
    - **Problem:** [what's wrong]
    - **Suggestion:** [how to fix]

    ### Issue 2: ...
    ```

    ## Constraints

    - Stay in your lane — only review for your specialization
    - Do NOT make changes — only suggest
    - Be constructive, not pedantic
    - Only flag issues that meaningfully affect quality
```
```

**Step 3: Write the code reviewer prompt template**

Write `skills/review-parallel/code-reviewer-prompt.md`:

```markdown
# Code Reviewer Agent Prompt Template

Use with Task tool (subagent_type: general-purpose):

```
description: "[Bug|Spec|Style|Security|Performance] review: [feature name]"
prompt: |
    You are a specialized code reviewer focusing on [SPECIALIZATION].

    ## Your Specialization: [ROLE]

    [For Bug Hunter:]
    Find: logic errors, off-by-one, null pointer, unhandled errors, race conditions,
    edge cases (empty collections, zero values, max values), resource leaks.

    [For Spec Checker:]
    Find: missing features from plan, extra features not in plan, behavior that
    doesn't match requirements, incorrect error messages, wrong return values.

    [For Style Checker:]
    Find: language rule violations, inconsistent naming, pattern deviations,
    missing type annotations, wrong import style, formatting issues.

    [For Security Reviewer:]
    Find: injection vulnerabilities (SQL, command, XSS), authentication gaps,
    authorization bypass, data exposure, insecure defaults, missing input validation.

    [For Performance Reviewer:]
    Find: O(n^2) or worse algorithms, unnecessary allocations, memory leaks,
    N+1 queries, missing caching opportunities, synchronous I/O in hot paths.

    ## Changes to Review

    [PASTE GIT DIFF or file contents HERE]

    ## Original Plan

    [PASTE PLAN SUMMARY for context]

    ## Language Rules

    [PASTE RELEVANT LANGUAGE RULES if Style Checker]

    ## Your Job

    1. Read ALL changes carefully
    2. Identify issues in your specialization area ONLY
    3. For each issue, be specific: file, line, what's wrong, how to fix
    4. Rate severity: critical (must fix), important (should fix), minor (nice to fix)

    ## CRITICAL: Output Format

    You MUST output your findings as a JSON array. This is required for the
    consensus mechanism to work.

    ```json
    [
        {
            "id": "[role]-1",
            "severity": "critical",
            "file": "src/auth.py",
            "line": 42,
            "description": "SQL injection via unsanitized user input in query builder",
            "suggestion": "Use parameterized queries instead of string concatenation"
        }
    ]
    ```

    Output an empty array `[]` if no issues found.

    ## Constraints

    - Stay in your lane — only review for your specialization
    - Be specific — file:line references required
    - No false positives — only flag real issues
    - Do NOT make changes
    - Output MUST be valid JSON
```
```

**Step 4: Write the consensus rules**

Write `skills/review-parallel/consensus-rules.md`:

```markdown
# Consensus Rules

## How the Orchestrator Processes Reviews

### Step 1: Collect All Issues

Parse the JSON arrays from all 5 code reviewers. Combine into a single list.

### Step 2: Group Similar Issues

Two issues are "similar" if:
- They reference the same file AND
- Their descriptions share the same core concern (use judgment)

Example: "SQL injection in auth.py:42" and "unsanitized input in auth.py line 42" → same issue.

### Step 3: Count Votes

For each unique issue group, count how many reviewers flagged it.

### Step 4: Apply Threshold

- **≥3 votes** → Write to `impl-tmp/todo.md` as mandatory fix
- **2 votes** → Write to `impl-tmp/review-notes.md` as "consider fixing"
- **1 vote** → Write to `impl-tmp/review-notes.md` as "informational"

### Step 5: Format todo.md

```markdown
# TODO: Issues to Fix (Iteration N)

## Issue 1: [description] (N/5 votes, severity: critical)
- **File:** `path/to/file:line`
- **Flagged by:** Bug Hunter, Spec Checker, Style Checker
- **Description:** [merged description]
- **Suggestion:** [best suggestion from reviewers]

## Issue 2: ...
```

### Step 6: Exit Criteria

- todo.md is empty → Done
- Iteration count reaches 5 → Done (report remaining issues)
- Same issues persist after 2 consecutive iterations → Escalate to user
```

**Step 5: Commit**

```bash
git add skills/review-parallel/ && git commit -m "feat: add review-parallel skill with reviewer prompts and consensus rules"
```

---

## Task 16: Validation script

**Files:**
- Create: `validate.sh`

**Step 1: Write the validation script**

Write `validate.sh` — a bash script that validates all components for correctness.

The script should:
- Accept flags: `--skills`, `--rules`, `--hooks`, `--smoke`, or no flag (validate all)
- Track pass/fail counts and report summary
- **Skill validation:** Check each `skills/*/SKILL.md` has YAML frontmatter with `name` and `description`, that description starts with "Use when", and that any referenced `.md` files in the same directory exist
- **Rule validation:** Check each `rules/*.md` has YAML frontmatter with `paths:` field containing glob patterns
- **Hook validation:** Check each `hooks/*.sh` is executable, has a valid shebang (`#!/usr/bin/env bash`), and for `auto-approve.sh` test that `echo '{"tool":"read_file"}' | hooks/auto-approve.sh` outputs valid JSON
- **Smoke test:** Create a temp dir, run `install.sh --target /tmp/test-install --non-interactive`, verify files were copied
- Print green PASS / red FAIL for each check, summary at end
- Exit code 0 if all pass, 1 if any fail

**Step 2: Make executable**

Run: `chmod +x validate.sh`

**Step 3: Run validation**

Run: `./validate.sh`
Expected: All checks pass (once all components are created)

**Step 4: Commit**

```bash
git add validate.sh && git commit -m "feat: add validation script for all components"
```

---

## Task 17: Installer script

**Files:**
- Create: `install.sh`

**Step 1: Write the installer script**

Write `install.sh` — an interactive bash script that installs components to a target location.

The script should:
- Accept `--target DIR` flag (default: current directory)
- Accept `--non-interactive` flag for CI/scripted use (installs everything)
- Accept `--dry-run` flag to preview changes without writing
- Accept `--uninstall` flag to remove installed components
- Show interactive menu (when not `--non-interactive`):
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
- **Language Rules:** Copy `rules/*.md` → `<target>/.claude/rules/`. Show diff if file exists. Backup existing.
- **Skills:** Copy `skills/*/` → `~/.claude/skills/`. Show diff if file exists. Backup existing.
- **Hooks:** Prompt for `CLAUDE_SLACK_WEBHOOK_URL`. Copy scripts to `~/.claude/hooks/`. Merge hook config from `templates/settings-hooks.json` into `~/.claude/settings.json` (preserve existing settings using `python3 -c` for JSON merge).
- **CLAUDE.md:** Copy `templates/CLAUDE.md.template` → `<target>/CLAUDE.md`. If exists, show diff and ask merge/replace/skip.
- Create `.bak.TIMESTAMP` backup before any overwrite
- Print summary of all changes at the end

**Step 2: Make executable**

Run: `chmod +x install.sh`

**Step 3: Test dry-run**

Run: `./install.sh --dry-run --non-interactive`
Expected: Shows what would be installed without writing files

**Step 4: Commit**

```bash
git add install.sh && git commit -m "feat: add interactive installer script"
```

---

## Task 18: Final validation and README

**Files:**
- Modify: `README.md`

**Step 1: Run full validation**

Run: `./validate.sh`
Expected: All checks pass

**Step 2: Update README.md**

Write `README.md` with:
- Project description (what this repo provides)
- Quick install: `./install.sh`
- Component overview (skills, rules, hooks, templates)
- The agentic workflow diagram (ASCII from design doc)
- Available language rules
- Hook descriptions and Slack setup instructions
- Validation: `./validate.sh`
- Contributing guidelines (skill format, rule format)

**Step 3: Final commit**

```bash
git add README.md && git commit -m "docs: add comprehensive README"
```

**Step 4: Run smoke test**

Run: `./validate.sh --smoke`
Expected: All smoke tests pass

---

## Dependency Graph

```
Task 1 (dirs) ──────> All other tasks depend on this
Tasks 2-5 (rules)     Independent, can be parallel
Task 6 (copy skills)  Independent
Task 7-8 (hooks)      Independent
Task 9-10 (templates) Independent
Task 11 (orchestrator) Depends on Tasks 12-15 being done (references their prompt files)
Task 12 (plan-codebase) Independent
Task 13 (plan-tests)    Independent
Task 14 (implement-parallel) Independent
Task 15 (review-parallel)    Independent
Task 16 (validate.sh)  Depends on Tasks 2-15 (validates them)
Task 17 (install.sh)   Depends on Tasks 2-15 (installs them)
Task 18 (README)        Depends on all above
```

## Step-by-Step Execution

| Step | Task(s) | What to Do | Files Created | Parallel? | Depends On | Commit Message |
|------|---------|-----------|---------------|-----------|------------|----------------|
| 1 | T1 | Create all directories (`skills/`, `rules/`, `hooks/`, `templates/` and subdirs) | 10 dirs | No | — | `chore: create directory structure` |
| 2a | T2 | Write `rules/python.md` with paths frontmatter + full Python rules (typing, ruff, pytest, pathlib, keyword-only params, modern syntax) | `rules/python.md` | Yes (2a-2d) | Step 1 | `feat: add Python language rules` |
| 2b | T3 | Write `rules/typescript.md` with paths frontmatter + TS rules (strict, pnpm, vitest, zod, Result types) | `rules/typescript.md` | Yes (2a-2d) | Step 1 | `feat: add TypeScript language rules` |
| 2c | T4 | Write `rules/rust.md` with paths frontmatter + Rust rules (clippy, Result, thiserror/anyhow, doc comments) | `rules/rust.md` | Yes (2a-2d) | Step 1 | `feat: add Rust language rules` |
| 2d | T5 | Write `rules/cpp.md` with paths frontmatter + C++ rules (C++20, smart ptrs, RAII, clang-format) | `rules/cpp.md` | Yes (2a-2d) | Step 1 | `feat: add C++ language rules` |
| 3 | T6 | Copy existing skills from `~/.claude/skills/` to `skills/clean-code-planner/SKILL.md` and `skills/python-coding-rules/SKILL.md` | 2 files | No | Step 1 | `feat: add existing skills` |
| 4a | T7 | Write `hooks/notify-slack.sh` (reads `CLAUDE_SLACK_WEBHOOK_URL`, sends POST to Slack on Notification/Stop events), `chmod +x` | `hooks/notify-slack.sh` | Yes (4a-4b) | Step 1 | `feat: add Slack notification hook` |
| 4b | T8 | Write `hooks/auto-approve.sh` (pattern-matches tool names, outputs `{"action":"allow"}` for safe ops), `chmod +x` | `hooks/auto-approve.sh` | Yes (4a-4b) | Step 1 | `feat: add auto-approve hook` |
| 5a | T9 | Write `templates/settings-hooks.json` with Notification, Stop, PermissionRequest hook config | `templates/settings-hooks.json` | Yes (5a-5b) | Step 4a-4b | `feat: add hook settings template` |
| 5b | T10 | Write `templates/CLAUDE.md.template` with workflow reference, language rules list, context management pattern | `templates/CLAUDE.md.template` | Yes (5a-5b) | Step 1 | `feat: add CLAUDE.md template` |
| 6a | T12 | Write `skills/plan-codebase/SKILL.md` (skill metadata) + `codebase-planner-prompt.md` (agent prompt: scan codebase, output code-spec.md) | 2 files | Yes (6a-6d) | Step 1 | `feat: add plan-codebase skill` |
| 6b | T13 | Write `skills/plan-tests/SKILL.md` (skill metadata) + `test-planner-prompt.md` (agent prompt: scan tests, output test-plan.md) | 2 files | Yes (6a-6d) | Step 1 | `feat: add plan-tests skill` |
| 6c | T14 | Write `skills/implement-parallel/SKILL.md` + `implementer-prompt.md` (impl coder) + `test-coder-prompt.md` (test coder) | 3 files | Yes (6a-6d) | Step 1 | `feat: add implement-parallel skill` |
| 6d | T15 | Write `skills/review-parallel/SKILL.md` + `refactor-reviewer-prompt.md` + `code-reviewer-prompt.md` + `consensus-rules.md` | 4 files | Yes (6a-6d) | Step 1 | `feat: add review-parallel skill` |
| 7 | T11 | Write `skills/implement-orchestrator/SKILL.md` — master orchestrator referencing all Phase 1-4 skills and their prompt templates | 1 file | No | Steps 6a-6d | `feat: add implement-orchestrator skill` |
| 8 | T16 | Write `validate.sh` — validates YAML frontmatter, file references, hook executability, JSON validity. Flags: `--skills`, `--rules`, `--hooks`, `--smoke`. `chmod +x`. Run it. | `validate.sh` | No | Steps 2-7 | `feat: add validation script` |
| 9 | T17 | Write `install.sh` — interactive menu (rules/skills/hooks/template/all), `--target`, `--dry-run`, `--non-interactive`, `--uninstall`, JSON merge for settings, backup before overwrite. `chmod +x`. Test `--dry-run`. | `install.sh` | No | Steps 2-7 | `feat: add interactive installer` |
| 10 | T18 | Update `README.md` with project description, install instructions, workflow diagram, component docs, contributing guide. Run `./validate.sh --smoke`. | `README.md` | No | Steps 8-9 | `docs: add comprehensive README` |

### Execution Summary

| Phase | Steps | Tasks | Files | Can Parallelize? |
|-------|-------|-------|-------|-----------------|
| **Foundation** | 1 | T1 | 10 dirs | No |
| **Language Rules** | 2a-2d | T2-T5 | 4 files | All 4 parallel |
| **Existing Skills** | 3 | T6 | 2 files | No |
| **Hooks** | 4a-4b | T7-T8 | 2 files | Both parallel |
| **Templates** | 5a-5b | T9-T10 | 2 files | Both parallel |
| **Workflow Skills** | 6a-6d | T12-T15 | 11 files | All 4 parallel |
| **Orchestrator** | 7 | T11 | 1 file | No (needs 6a-6d) |
| **Validation** | 8 | T16 | 1 file | No (needs 2-7) |
| **Installer** | 9 | T17 | 1 file | No (needs 2-7) |
| **Documentation** | 10 | T18 | 1 file | No (needs 8-9) |
| **TOTAL** | **10 steps** | **18 tasks** | **~35 files** | |
