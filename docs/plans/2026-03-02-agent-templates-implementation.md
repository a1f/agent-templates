# Agent Templates Implementation Plan (v2)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a shareable repo of Claude Code skills, hooks, rules, and an installer — centered around a multi-phase agentic implementation workflow. All decisions are backed by research in `docs/research/`.

**Architecture:** Flat-by-type repo structure (`skills/`, `rules/`, `hooks/`, `templates/`). Skills follow the SKILL.md format (YAML frontmatter + markdown). Rules use comma-separated `paths:` frontmatter. Installer is an interactive bash script (bash 3.2 compatible). Validation script checks all artifacts.

**Tech Stack:** Bash, SKILL.md format, JSON (settings/hooks config), jq (for JSON merging)

---

## Task 1: Create directory structure

**Files:**
- Create directories: `skills/`, `rules/`, `hooks/`, `templates/`

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

Run: `find . -type d -not -path './.git/*' -not -path './docs/*' | sort`
Expected: all skill, rule, hook, and template directories listed.

**Step 3: Commit**

```bash
git add -A && git commit -m "chore: create directory structure for agent-templates"
```

---

## Task 2: Python language rule

> **Research:** `docs/research/python-best-practices.md`, `docs/research/claude-code-rules.md`
>
> **Format:** Comma-separated paths (not YAML arrays). See research for known parsing bug.

**Files:**
- Create: `rules/python.md`

**Step 1: Write the rule file**

Write `rules/python.md` with the following content. Use comma-separated `paths:` in frontmatter. Include all rules from research findings:

- **Target:** Python 3.12+
- **Tooling:** ruff (`select = ["E", "F", "I", "B", "C4", "UP", "SIM", "PIE", "RUF"]`), mypy strict, uv, pytest + hypothesis + pytest-asyncio
- **Typing:** Modern syntax (`list[T]`, `T | None`, `type` statement for aliases), `TypeIs` over `TypeGuard`, `Self` for return-self, `Protocol` over ABC, `ParamSpec` for decorators, `@override`
- **Parameters:** Keyword-only (`*` first param for >2-3 args), no mutable defaults (use `None` sentinel), allow sensible immutable defaults
- **Structure:** Empty `__init__.py`, `types.py` for types, `constants.py` with `Final[T]`, all config in `pyproject.toml`
- **Functions over classes** unless stateful
- **Logging:** structlog with JSON output, log to stdout, bind context at entry points
- **Error handling:** Project exception hierarchies, `raise X from Y`, `except*`/`ExceptionGroup` for concurrent errors
- **Docstrings:** Single sentence explaining WHY, no Args/Returns
- **Code health:** ruff + mypy + pytest + hypothesis, branch coverage, `filterwarnings = ["error"]`

**Step 2: Verify frontmatter format**

Run: `head -5 rules/python.md`
Expected: `---` / `paths: "**/*.py", "**/pyproject.toml"` / `---`

**Step 3: Commit**

```bash
git add rules/python.md && git commit -m "feat: add Python language rule with 2025 best practices"
```

---

## Task 3: TypeScript language rule

> **Research:** `docs/research/typescript-best-practices.md`, `docs/research/claude-code-rules.md`

**Files:**
- Create: `rules/typescript.md`

**Step 1: Write the rule file**

Write `rules/typescript.md`. Include:

- **Target:** TypeScript 5.8+, `module: "nodenext"` or `module: "esnext"`
- **Strict mode:** `strict: true` + `noUncheckedIndexedAccess` + `exactOptionalPropertyTypes` + `noPropertyAccessFromIndexSignature`
- **Tooling:** Biome (preferred) or ESLint+Prettier, pnpm, vitest, Zod (Standard Schema compliant)
- **No enums:** Use `as const` objects with derived union types. Include the canonical pattern:
  ```typescript
  const Status = { Active: "active", Inactive: "inactive" } as const;
  type Status = (typeof Status)[keyof typeof Status];
  ```
- **No barrel exports:** Direct file imports. Barrels only at package public API boundaries.
- **`unknown` over `any`:** When dynamic type needed, use `unknown` with type narrowing.
- **Result types:** neverthrow or custom discriminated union for expected errors.
- **const over let**, never `var`
- **Monorepo:** Turborepo for TypeScript monorepos
- **No CommonJS** for new code

**Step 2: Verify frontmatter**

Run: `head -5 rules/typescript.md`
Expected: `---` / `paths: "**/*.ts", "**/*.tsx", "**/package.json"` / `---`

**Step 3: Commit**

```bash
git add rules/typescript.md && git commit -m "feat: add TypeScript language rule with Biome and strict patterns"
```

---

## Task 4: Rust language rule

> **Research:** `docs/research/rust-best-practices.md`, `docs/research/claude-code-rules.md`

**Files:**
- Create: `rules/rust.md`

**Step 1: Write the rule file**

Write `rules/rust.md`. Include:

- **Target:** Edition 2024 (Rust 1.85+), specify `rust-version` in Cargo.toml
- **Tooling:** cargo fmt + cargo clippy before commit, Tokio for async (async-std discontinued), thiserror + anyhow, proptest, cargo-nextest
- **Error handling:** `Result<T,E>` in public APIs, thiserror for libraries, anyhow for apps, mention eyre as alternative
- **Documentation:** Doc comments on all public items with `# Errors`, `# Panics`, `# Safety` sections
- **`#[must_use]`** on functions with important return values
- **Iterators over explicit loops**
- **Unsafe discipline:** `unsafe_code = "deny"` in workspace lints, `// SAFETY:` comments mandatory, `#[forbid(unsafe_code)]` for pure-safe crates
- **Workspace lints:** Configure via `[workspace.lints]` in Cargo.toml (not inline attributes). Cherry-pick from pedantic: `doc_markdown`, `manual_let_else`, `match_same_arms`, `redundant_closure_for_method_calls`, `semicolon_if_nothing_returned`, `must_use_candidate`, `needless_pass_by_value`, `uninlined_format_args`
- **Async:** Native `async fn` in traits (stable), `#[async_trait]` only for dyn-compatible traits. `tokio::select!`, `tokio::sync::mpsc`, `spawn_blocking` for CPU work
- **Serde:** `rename_all = "camelCase"` for APIs, `deny_unknown_fields` for configs, avoid `deny_unknown_fields` + `flatten` combo
- **No `println!` in library code** — use `log`/`tracing`
- **Workspace structure:** Virtual manifest, flat `crates/` layout, shared `[workspace.dependencies]`
- **Supply chain:** `cargo audit` + `cargo deny` in CI

**Step 2: Verify frontmatter**

Run: `head -5 rules/rust.md`
Expected: `---` / `paths: "**/*.rs", "**/Cargo.toml"` / `---`

**Step 3: Commit**

```bash
git add rules/rust.md && git commit -m "feat: add Rust language rule targeting edition 2024"
```

---

## Task 5: C++ language rule

> **Research:** `docs/research/cpp-best-practices.md`, `docs/research/claude-code-rules.md`

**Files:**
- Create: `rules/cpp.md`

**Step 1: Write the rule file**

Write `rules/cpp.md`. Include:

- **Target:** C++20 minimum, CMake 3.28+
- **Tooling:** clang-format + clang-tidy (`modernize-*`, `bugprone-*`, `performance-*`, `readability-*`, `cppcoreguidelines-*`), GoogleTest, vcpkg (or Conan 2)
- **Smart pointers:** `unique_ptr` default, `shared_ptr` when needed, `weak_ptr` to break cycles
- **RAII** for all resource management
- **constexpr/const** wherever possible
- **C++20 features:** concepts over SFINAE, `std::format` over printf/iostream, `std::span` for buffers, `std::string_view` for non-owning strings, designated initializers, three-way comparison, `[[nodiscard]]` with message
- **C++23 where available:** `std::expected` for error handling, monadic `std::optional`, `std::print`/`std::println`
- **CMake:** Modern target-based (`target_link_libraries`, `target_compile_features`), `CMakePresets.json`, never `file(GLOB)` for sources
- **Compiler warnings:** `-Wall -Wextra -Wpedantic -Werror` in CI
- **Sanitizers:** ASan+UBSan together in debug, TSan separately (can't combine with ASan)
- **Ranges** for data transformation pipelines (not needed for simple loops)
- **Modules:** NOT default. Consider only for greenfield with CMake 4.0+
- **Coroutines:** Only with library support (cppcoro, Asio)

**Step 2: Verify frontmatter**

Run: `head -5 rules/cpp.md`
Expected: `---` / `paths: "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp", "**/CMakeLists.txt"` / `---`

**Step 3: Commit**

```bash
git add rules/cpp.md && git commit -m "feat: add C++ language rule targeting C++20"
```

---

## Task 6: Package existing skills (clean-code-planner + python-coding-rules)

> **Research:** `docs/research/claude-code-skills.md` (SKILL.md format, CSO principles)

**Files:**
- Create: `skills/clean-code-planner/SKILL.md` (copy from `~/.claude/skills/clean-code-planner/SKILL.md`)
- Create: `skills/python-coding-rules/SKILL.md` (copy from `~/.claude/skills/python-coding-rules/SKILL.md`, update with research findings)

**Step 1: Copy clean-code-planner**

Copy the existing `~/.claude/skills/clean-code-planner/SKILL.md` to `skills/clean-code-planner/SKILL.md`. This skill is already well-structured with proper frontmatter. No changes needed.

**Step 2: Copy and update python-coding-rules**

Copy `~/.claude/skills/python-coding-rules/SKILL.md` to `skills/python-coding-rules/SKILL.md`. Apply the research-driven updates:

1. **Relax "no default values" rule:** Change from "Never use literals or constants as default parameter values" to "Never use mutable defaults (lists, dicts, sets). Use `None` sentinel for optional params. Allow sensible immutable defaults (bool, int, str)."
2. **Add type checker requirement:** Add a section for "Run mypy with `strict = true` or pyright strict mode."
3. **Add uv:** "Use uv for package management, virtual environments, and Python version management."
4. **Add structlog:** "Use structlog with JSON output for structured logging."
5. **Add Protocol:** "Prefer `Protocol` for interfaces (structural subtyping) unless sharing implementation via ABC."
6. **Add modern typing:** `TypeIs` over `TypeGuard`, `type` statement for aliases, `Self` for return-self, `ParamSpec` for decorators, `@override` on overriding methods.
7. **Add error handling:** "Define project exception hierarchies. Chain exceptions with `raise X from Y`. Use `except*`/`ExceptionGroup` for concurrent errors."
8. **Add testing:** hypothesis for property-based, pytest-asyncio for async, `filterwarnings = ["error"]`, branch coverage.
9. **Add pyproject.toml:** "All tool config in `pyproject.toml`."
10. **Add ruff rule set:** `select = ["E", "F", "I", "B", "C4", "UP", "SIM", "PIE", "RUF"]`
11. **Target Python 3.12+** explicitly.

**Step 3: Verify both skills have valid frontmatter**

Run: `head -4 skills/clean-code-planner/SKILL.md && head -4 skills/python-coding-rules/SKILL.md`
Expected: Both have `---` / `name:` / `description: Use when...` / `---`

**Step 4: Commit**

```bash
git add skills/clean-code-planner/ skills/python-coding-rules/ && git commit -m "feat: package clean-code-planner and updated python-coding-rules skills"
```

---

## Task 7: Slack notification hook

> **Research:** `docs/research/slack-webhooks.md`, `docs/research/claude-code-hooks.md`

**Files:**
- Create: `hooks/notify-slack.sh`

**Step 1: Write the hook script**

Write `hooks/notify-slack.sh`. Must follow these specifications:

- Shebang: `#!/usr/bin/env bash` + `set -euo pipefail`
- Reads event type from `$1` (passed by settings.json command: `notify-slack.sh notification` or `notify-slack.sh stop`)
- Reads `CLAUDE_SLACK_WEBHOOK_URL` env var
- Silently exits (`exit 0`) if webhook URL not set
- Extracts project directory name from `$PWD`
- Generates UTC timestamp with `date -u +"%Y-%m-%d %H:%M UTC"`
- Builds JSON payload with simple `"text"` field (notification fallback) + `"blocks"` array (Block Kit section with mrkdwn)
- Sends via `curl -s -o /dev/null -w "%{http_code}"` with:
  - `-X POST`
  - `-H "Content-type: application/json"`
  - `--max-time 5` (5-second timeout)
  - `--data "$PAYLOAD"`
- Captures HTTP status code
- On non-200: logs to stderr with masked webhook URL (last 6 chars only)
- Exit code 0 always (never blocks Claude)

**Step 2: Make executable**

```bash
chmod +x hooks/notify-slack.sh
```

**Step 3: Test manually**

Run: `CLAUDE_SLACK_WEBHOOK_URL="" ./hooks/notify-slack.sh stop`
Expected: Exits silently with code 0 (no webhook URL set)

Run: `./hooks/notify-slack.sh stop`
Expected: Exits silently with code 0 (no env var at all)

**Step 4: Commit**

```bash
git add hooks/notify-slack.sh && git commit -m "feat: add Slack notification hook with Block Kit support"
```

---

## Task 8: Auto-approve hook

> **Research:** `docs/research/claude-code-hooks.md`

**Files:**
- Create: `hooks/auto-approve.sh`

**Step 1: Write the hook script**

Write `hooks/auto-approve.sh`. Must follow these specifications:

- Shebang: `#!/usr/bin/env bash` + `set -euo pipefail`
- Reads JSON from stdin
- Extracts `tool_name` with: `tool_name=$(echo "$input" | jq -r '.tool_name // ""')`
- Safe tools list (auto-approve): `Read`, `Glob`, `Grep`, `LS`, `WebSearch`, `WebFetch`, `NotebookRead`
- For safe tools: output `{"hookSpecificOutput":{"permissionDecision":"allow"}}` to stdout and exit 0
- For all other tools: exit 0 with no output (falls through to user prompt)
- If jq is not available: exit 0 with no output (fail open, don't block)

**Step 2: Make executable**

```bash
chmod +x hooks/auto-approve.sh
```

**Step 3: Test with mock input**

Run: `echo '{"tool_name":"Read","tool_input":{}}' | ./hooks/auto-approve.sh`
Expected: `{"hookSpecificOutput":{"permissionDecision":"allow"}}`

Run: `echo '{"tool_name":"Write","tool_input":{}}' | ./hooks/auto-approve.sh`
Expected: No output, exit code 0

**Step 4: Commit**

```bash
git add hooks/auto-approve.sh && git commit -m "feat: add auto-approve hook for safe read-only tools"
```

---

## Task 9: Settings hook template

> **Research:** `docs/research/claude-code-hooks.md`, `docs/research/claude-code-settings.md`

**Files:**
- Create: `templates/settings-hooks.json`

**Step 1: Write the settings template**

Write `templates/settings-hooks.json` with the hook configuration from the design doc. Event matchers: empty string `""` for Notification/Stop (matches all), empty string for PreToolUse (matches all tools — the script itself filters).

**Step 2: Validate JSON**

Run: `jq . templates/settings-hooks.json`
Expected: Pretty-printed valid JSON

**Step 3: Commit**

```bash
git add templates/settings-hooks.json && git commit -m "feat: add settings.json hook configuration template"
```

---

## Task 10: CLAUDE.md template

> **Research:** `docs/research/claude-code-settings.md`

**Files:**
- Create: `templates/CLAUDE.md.template`

**Step 1: Write the template**

Write `templates/CLAUDE.md.template` with:

- Project overview placeholder (`{{PROJECT_NAME}}`)
- Tech stack placeholder
- Build/test/lint commands section (placeholder)
- Reference to installed language rules: "Language-specific rules are in `.claude/rules/` and load automatically when editing matching files."
- Reference to agentic workflow: "Use `/implement-orchestrator` to execute plans through the 4-phase agentic pipeline."
- Skill entry points list
- Context management pattern: "For long tasks, use `impl-tmp/progress.md` to track state. Use `/clear` then continue with the progress file."
- Keep under 50 lines

**Step 2: Verify it's readable**

Run: `wc -l templates/CLAUDE.md.template`
Expected: Under 50 lines

**Step 3: Commit**

```bash
git add templates/CLAUDE.md.template && git commit -m "feat: add CLAUDE.md starter template"
```

---

## Task 11: Validation script

> **Research:** `docs/research/validation-patterns.md`

**Files:**
- Create: `validate.sh`

**Step 1: Write validate.sh**

Write `validate.sh` as a bash script (bash 3.2 compatible). Include:

**CLI parsing:**
```bash
for arg in "$@"; do
  case "$arg" in
    --skills) VALIDATE_SKILLS=true ;;
    --rules) VALIDATE_RULES=true ;;
    --hooks) VALIDATE_HOOKS=true ;;
    --smoke) VALIDATE_SMOKE=true ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done
# If no flags, validate everything
if [[ -z "${VALIDATE_SKILLS:-}" && ... ]]; then VALIDATE_ALL=true; fi
```

**Skill validation (`validate_skills`):**
- Find all `skills/*/SKILL.md` files
- For each: extract frontmatter with `sed`, check `name:` and `description:` fields exist, check description starts with "Use when"
- Check referenced prompt template files exist (parse `SKILL.md` body for `.md` file references within the same skill directory)
- Count pass/fail

**Rule validation (`validate_rules`):**
- Find all `rules/*.md` files
- For each: extract frontmatter, check `paths:` field exists, verify it uses comma-separated format (not YAML array)
- Count pass/fail

**Hook validation (`validate_hooks`):**
- Find all `hooks/*.sh` files
- For each: check file is executable, check has `#!/usr/bin/env bash` shebang
- Run ShellCheck if available: `shellcheck --severity=warning --shell=bash "$file"`
- For auto-approve.sh: test with mock JSON input, validate output is valid JSON
- For notify-slack.sh: test with no webhook URL set, verify silent exit
- Count pass/fail

**Settings validation (`validate_settings`):**
- Check `templates/settings-hooks.json` is valid JSON with `jq .`
- Check hook event types are from known list

**Smoke test (`validate_smoke`):**
- Create temp dir with `mktemp -d` + `trap` cleanup
- Run `./install.sh --target="$tmpdir" --non-interactive --all` (requires install.sh to exist first)
- Verify expected files exist
- Verify hooks executable
- Verify JSON valid

**Step 2: Make executable**

```bash
chmod +x validate.sh
```

**Step 3: Run validation (skills won't all exist yet, but rules and hooks should pass)**

Run: `./validate.sh --rules --hooks`
Expected: All rules pass (4 files), all hooks pass (2 files)

**Step 4: Commit**

```bash
git add validate.sh && git commit -m "feat: add validation script with skill, rule, hook, and smoke checks"
```

---

## Task 12: Skill — implement-orchestrator

> **Research:** `docs/research/agent-orchestration.md`, `docs/research/code-review-automation.md`, `docs/research/claude-code-skills.md`

**Files:**
- Create: `skills/implement-orchestrator/SKILL.md`

**Step 1: Write the SKILL.md**

This is the master orchestrator skill. It coordinates the 4-phase pipeline. Include:

**Frontmatter:**
```yaml
---
name: implement-orchestrator
description: Use when the user asks to implement a plan using the agentic workflow, or invokes /implement-orchestrator, or says "implement this plan" or "execute this plan with agents"
---
```

**Body structure:**
1. `# Implement Orchestrator` — overview of the 4-phase pipeline
2. `## Prerequisites` — approved plan.md must exist
3. `## Phase 1: Planning` — dispatch 2 parallel subagents (plan-codebase + plan-tests), write to `impl-tmp/`, create manifest.json
4. `## Phase 2: Implementation` — dispatch 2 parallel subagents (impl coder + test coder) with code-spec.md and test-plan.md as input
5. `## Phase 3: Refactoring Review` — dispatch 3 parallel reviewers (Architecture, DRY, Simplification), merge results to refactor-suggestions.md, dispatch impl+test coders to apply suggestions
6. `## Phase 4: Code Review Loop` — dispatch 5 parallel reviewers, apply severity-based consensus, generate todo.md, loop max 3 times
7. `## Error Recovery` — 3-tier strategy (retry, checkpoint, graceful degradation)
8. `## State Management` — impl-tmp/ directory layout, manifest.json format, checkpoint.json
9. Cross-reference other skills with `REQUIRED SUB-SKILL:` syntax

**Key details to include:**
- Exact subagent dispatch pattern using Claude Code Task tool
- manifest.json schema
- checkpoint.json schema
- Consensus rules (inline, not separate file — keeps skill self-contained)
- Early exit conditions: todo.md empty or <2 issues
- Iteration 3 escalation: report remaining critical issues to human

**Step 2: Verify frontmatter**

Run: `head -4 skills/implement-orchestrator/SKILL.md`

**Step 3: Run validation**

Run: `./validate.sh --skills`

**Step 4: Commit**

```bash
git add skills/implement-orchestrator/ && git commit -m "feat: add implement-orchestrator master skill for 4-phase pipeline"
```

---

## Task 13: Skill — plan-codebase

> **Research:** `docs/research/agent-orchestration.md`, `docs/research/claude-code-skills.md`

**Files:**
- Create: `skills/plan-codebase/SKILL.md`
- Create: `skills/plan-codebase/codebase-planner-prompt.md`

**Step 1: Write SKILL.md**

**Frontmatter:**
```yaml
---
name: plan-codebase
description: Use when dispatched by implement-orchestrator to create a code specification from an approved plan, or when you need to analyze a codebase and produce a detailed implementation specification
---
```

**Body:** Instructions for a subagent to:
1. Read the plan.md
2. Scan the codebase for existing functions, patterns, and reuse opportunities
3. List exact files to create/modify/delete
4. Write pseudo-code or code skeleton for each change
5. Apply clean-code-planner principles
6. Output structured code-spec.md with file-by-file change descriptions

**Step 2: Write codebase-planner-prompt.md**

The agent prompt template that implement-orchestrator passes to the subagent. Includes: plan.md reference, output format specification, codebase exploration instructions.

**Step 3: Verify and commit**

```bash
./validate.sh --skills
git add skills/plan-codebase/ && git commit -m "feat: add plan-codebase skill for Phase 1 code planning"
```

---

## Task 14: Skill — plan-tests

> **Research:** `docs/research/agent-orchestration.md`, `docs/research/claude-code-skills.md`

**Files:**
- Create: `skills/plan-tests/SKILL.md`
- Create: `skills/plan-tests/test-planner-prompt.md`

**Step 1: Write SKILL.md**

**Frontmatter:**
```yaml
---
name: plan-tests
description: Use when dispatched by implement-orchestrator to create a test plan from an approved plan, or when you need to design a comprehensive test strategy for a feature
---
```

**Body:** Instructions for a subagent to:
1. Read the plan.md
2. Find existing test patterns, framework, fixtures
3. Define test cases per requirement
4. Specify fixtures, mocks, test structure
5. Apply language-specific testing best practices (reference rules/)
6. Output structured test-plan.md

**Step 2: Write test-planner-prompt.md**

Agent prompt template. Includes: plan.md reference, output format, testing framework detection instructions.

**Step 3: Verify and commit**

```bash
./validate.sh --skills
git add skills/plan-tests/ && git commit -m "feat: add plan-tests skill for Phase 1 test planning"
```

---

## Task 15: Skill — implement-parallel

> **Research:** `docs/research/agent-orchestration.md`, `docs/research/claude-code-skills.md`

**Files:**
- Create: `skills/implement-parallel/SKILL.md`
- Create: `skills/implement-parallel/implementer-prompt.md`
- Create: `skills/implement-parallel/test-coder-prompt.md`

**Step 1: Write SKILL.md**

**Frontmatter:**
```yaml
---
name: implement-parallel
description: Use when dispatched by implement-orchestrator to execute code-spec.md and test-plan.md with parallel coders, or when you need to implement code and tests from specifications simultaneously
---
```

**Body:** Instructions for dispatching 2 parallel subagents:
1. Impl Coder: reads code-spec.md, writes implementation files, follows language rules, commits
2. Test Coder: reads test-plan.md, writes test files, follows TDD, commits
3. No worktrees needed (different file types)
4. Error handling: if one fails, continue with other, retry failed one

**Step 2: Write implementer-prompt.md and test-coder-prompt.md**

Agent prompt templates for each coder subagent.

**Step 3: Verify and commit**

```bash
./validate.sh --skills
git add skills/implement-parallel/ && git commit -m "feat: add implement-parallel skill for Phase 2 coding"
```

---

## Task 16: Skill — review-parallel

> **Research:** `docs/research/code-review-automation.md`, `docs/research/agent-orchestration.md`, `docs/research/claude-code-skills.md`

**Files:**
- Create: `skills/review-parallel/SKILL.md`
- Create: `skills/review-parallel/refactor-reviewer-prompt.md`
- Create: `skills/review-parallel/code-reviewer-prompt.md`
- Create: `skills/review-parallel/consensus-rules.md`

**Step 1: Write SKILL.md**

**Frontmatter:**
```yaml
---
name: review-parallel
description: Use when dispatched by implement-orchestrator to run parallel code reviews with severity-based consensus, or when you need to coordinate multiple specialized code reviewers on a set of changes
---
```

**Body:** Instructions for:
1. **Phase 3 (Refactoring):** Dispatch 3 reviewers (Architecture, DRY, Simplification), merge to refactor-suggestions.md
2. **Phase 4 (Code Review):** Dispatch 5 independent reviewers (Correctness, Spec Compliance, Security, Maintainability, Performance)
3. **Consensus:** Apply severity-based rules from consensus-rules.md
4. **Output:** Generate todo.md with issues ordered by severity, then vote count
5. **Actionability check:** Post-filter with "Would a senior engineer change code based on this?"
6. **Loop control:** Early exit if <2 issues; max 3 iterations; diff-only on iterations 2-3

**Step 2: Write refactor-reviewer-prompt.md**

Template for Phase 3 reviewers. Three sections (Architecture, DRY, Simplification) each with specific focus areas and output format.

**Step 3: Write code-reviewer-prompt.md**

Template for Phase 4 reviewers. Five sections (Correctness, Spec Compliance, Security, Maintainability, Performance) each with:
- Specific focus area and what to look for
- What NOT to flag (to reduce false positives)
- Output format: `[{file, line, issue, severity, category}]`
- Severity definitions: CRITICAL, MAJOR, MINOR, LOW

**Step 4: Write consensus-rules.md**

Document the severity-based consensus algorithm:
```
1. Each reviewer outputs: [{file, line, issue, severity, category}]
2. Group by (file, line_range) — within 5 lines = "same location"
3. For each group:
   a. Count distinct reviewers who flagged it
   b. Take highest severity assigned
   c. Apply threshold: CRITICAL≥1, MAJOR≥2, MINOR≥3
4. Run survivors through actionability check
5. Write to todo.md ordered by severity desc, then vote_count desc
6. Early exit: if total < 2 issues, stop iterating
7. Hard cap: 3 iterations
```

**Step 5: Verify and commit**

```bash
./validate.sh --skills
git add skills/review-parallel/ && git commit -m "feat: add review-parallel skill with severity-based consensus"
```

---

## Task 17: Installer script

> **Research:** `docs/research/installer-patterns.md`, `docs/research/claude-code-settings.md`

**Files:**
- Create: `install.sh`

**Step 1: Write install.sh**

Write `install.sh` as a bash 3.2-compatible interactive installer. Structure:

**Header/setup:**
- Shebang: `#!/usr/bin/env bash` + `set -euo pipefail`
- Bash version check: `if [[ "${BASH_VERSINFO[0]}" -lt 3 ]]; then echo "Error: bash 3.2+ required"; exit 1; fi`
- Parse CLI flags: `--dry-run`, `--uninstall`, `--target=<path>`, `--non-interactive`, `--all`
- Set `SCRIPT_DIR` to directory containing install.sh
- Set `BACKUP_MANIFEST` path

**Helper functions:**
- `backup_file()` — timestamped backup with manifest recording
- `install_file()` — dry-run aware copy with backup
- `show_diff()` — show diff if target exists
- `rollback()` — read manifest and restore originals (for `--uninstall` or `trap ERR`)

**Component installers:**
- `install_rules()` — copies `rules/*.md` → `<target>/.claude/rules/`
- `install_skills()` — copies `skills/*/` → `~/.claude/skills/`
- `install_hooks()` — copies `hooks/*.sh` → `~/.claude/hooks/`, prompts for Slack webhook URL, deep-merges settings.json with `jq -s '.[0] * .[1]'` (falls back to manual merge instructions if jq not found)
- `install_template()` — copies `templates/CLAUDE.md.template` → `<target>/CLAUDE.md`, shows diff if exists

**Menu (interactive mode):**
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

Use `read -rp` for input. Parse comma-separated choices.

**Non-interactive mode:** `--non-interactive --all` installs everything without prompts.

**Step 2: Make executable**

```bash
chmod +x install.sh
```

**Step 3: Test dry-run**

Run: `./install.sh --dry-run --non-interactive --all --target=/tmp/test-install`
Expected: Shows `[DRY RUN]` messages for each file, no actual files created.

**Step 4: Commit**

```bash
git add install.sh && git commit -m "feat: add interactive installer with dry-run, backup, and merge support"
```

---

## Task 18: Smoke test and full validation

**Files:**
- Modify: `validate.sh` (add smoke test now that install.sh exists)

**Step 1: Update validate.sh smoke test**

The `--smoke` flag should now work since install.sh exists. Verify the smoke test function:
1. Creates temp dir
2. Runs `./install.sh --target="$tmpdir" --non-interactive --all`
3. Checks all expected files exist
4. Checks hooks executable
5. Checks JSON valid
6. Cleans up

**Step 2: Run full validation**

Run: `./validate.sh`
Expected: All skills, rules, hooks, and settings pass validation.

Run: `./validate.sh --smoke`
Expected: Smoke test installs to temp dir and all files verified.

**Step 3: Fix any issues found**

If validation reveals problems, fix them before committing.

**Step 4: Commit**

```bash
git add validate.sh && git commit -m "feat: complete smoke test integration in validation script"
```

---

## Task 19: README

**Files:**
- Modify: `README.md`

**Step 1: Write comprehensive README**

Write `README.md` with:

- Project title and one-line description
- Quick start: `./install.sh` → select components
- Components overview (skills, rules, hooks, templates) with brief descriptions
- Agentic workflow diagram (ASCII art from design doc)
- Language rules table (Python, TypeScript, Rust, C++)
- Hook descriptions (Slack notification, auto-approve)
- Installation details per component
- Validation: `./validate.sh` and `./validate.sh --smoke`
- Research documents reference
- Contributing section

**Step 2: Commit**

```bash
git add README.md && git commit -m "docs: add comprehensive README with workflow diagram and component docs"
```

---

## Task 20: Final validation and cleanup

**Step 1: Run full validation suite**

```bash
./validate.sh
./validate.sh --smoke
```

Expected: All checks pass, smoke test succeeds.

**Step 2: Review file count**

```bash
find . -type f -not -path './.git/*' | wc -l
```

Expected: ~30-35 files total (13 research docs, 2 plan docs, 1 design doc, 4 rules, 7 skills with supporting files, 2 hooks, 2 templates, installer, validator, README).

**Step 3: Final commit if any cleanup needed**

```bash
git add -A && git commit -m "chore: final cleanup and validation pass"
```

---

## Execution Order and Dependencies

| Task | Name | Files | Depends On | Parallel Group |
|------|------|-------|-----------|---------------|
| 1 | Directory structure | dirs | — | A |
| 2 | Python rule | `rules/python.md` | 1 | B |
| 3 | TypeScript rule | `rules/typescript.md` | 1 | B |
| 4 | Rust rule | `rules/rust.md` | 1 | B |
| 5 | C++ rule | `rules/cpp.md` | 1 | B |
| 6 | Package existing skills | `skills/clean-code-planner/`, `skills/python-coding-rules/` | 1 | B |
| 7 | Slack hook | `hooks/notify-slack.sh` | 1 | B |
| 8 | Auto-approve hook | `hooks/auto-approve.sh` | 1 | B |
| 9 | Settings template | `templates/settings-hooks.json` | 1 | B |
| 10 | CLAUDE.md template | `templates/CLAUDE.md.template` | 1 | B |
| 11 | Validation script | `validate.sh` | 2-10 | C |
| 12 | implement-orchestrator | `skills/implement-orchestrator/` | 1, 11 | D |
| 13 | plan-codebase | `skills/plan-codebase/` | 1, 11 | D |
| 14 | plan-tests | `skills/plan-tests/` | 1, 11 | D |
| 15 | implement-parallel | `skills/implement-parallel/` | 1, 11 | D |
| 16 | review-parallel | `skills/review-parallel/` | 1, 11 | D |
| 17 | Installer | `install.sh` | 2-10 | C |
| 18 | Smoke test | `validate.sh` update | 11, 17 | E |
| 19 | README | `README.md` | all | F |
| 20 | Final validation | — | all | F |

**Parallel groups:** Tasks in the same group can run as parallel subagents.
- **Group B** (tasks 2-10): All independent, can run in parallel after directory structure
- **Group D** (tasks 12-16): All skill files, can run in parallel after validation script exists
