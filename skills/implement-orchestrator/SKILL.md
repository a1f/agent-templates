---
name: implement-orchestrator
description: Use when the user asks to implement a plan using the agentic workflow, or invokes /implement-orchestrator, or says "implement this plan" or "execute this plan with agents"
---

# Implement Orchestrator

Master orchestrator for the 4-phase agentic implementation pipeline. Coordinates parallel subagents, manages state via `impl-tmp/`, and enforces quality through iterative code review.

```
plan.md --> [Phase 1: Planning] --> [Phase 2: Implementation] --> [Phase 3: Refactoring] --> [Phase 4: Review Loop] --> Done
               2 agents ||            2 agents ||                  3 reviewers ||              5 reviewers ||
```

## Prerequisites

An approved `plan.md` must exist in the working directory. Abort with a clear message if missing.

## Phase 1: Planning

Dispatch 2 parallel subagents via the Task tool:

1. **Plan-Codebase** agent -- reads `plan.md`, writes `impl-tmp/code-spec.md`
2. **Plan-Tests** agent -- reads `plan.md`, writes `impl-tmp/test-plan.md`

**REQUIRED SUB-SKILL:** plan-codebase
**REQUIRED SUB-SKILL:** plan-tests

On completion, write `impl-tmp/manifest.json`:
```json
{"phase":1,"status":"complete","outputs":{"code_spec":"impl-tmp/code-spec.md","test_plan":"impl-tmp/test-plan.md"},"timestamp":"<ISO-8601>"}
```

## Phase 2: Implementation

Dispatch 2 parallel subagents:

1. **Impl Coder** -- reads `code-spec.md`, writes source files
2. **Test Coder** -- reads `test-plan.md`, writes test files

**REQUIRED SUB-SKILL:** implement-parallel

Update `manifest.json` with phase 2 status and output file list.

## Phase 3: Refactoring Review

Dispatch 3 parallel reviewers (Architecture, DRY, Simplification). Each writes findings to `impl-tmp/refactor-review-{name}.md`. Merge results into `impl-tmp/refactor-suggestions.md`. Re-dispatch impl + test coders to apply accepted suggestions.

## Phase 4: Code Review Loop

Dispatch 5 independent parallel reviewers (Correctness, Spec Compliance, Security, Maintainability, Performance). Each outputs `[{file, line, issue, severity, category}]`.

**REQUIRED SUB-SKILL:** review-parallel

**Consensus rules:**
```
CRITICAL (security, crashes, data corruption): >=1 reviewer --> todo.md
MAJOR (logic errors, spec violations):         >=2 reviewers --> todo.md
MINOR (maintainability, minor perf):           >=3 reviewers --> todo.md
LOW (style nits, suggestions):                 Logged only, not required
```
Issues grouped by code location (within 5 lines = same location). Highest severity assigned to each group. Actionability check: "Would a senior engineer change code based on this?"

**Early exit:** `todo.md` empty or <2 issues.
**Max iterations:** 3. On iteration 3, escalate remaining critical issues to human.

Re-dispatch impl + test coders with `todo.md` after each iteration.

## Error Recovery

3-tier strategy:
1. **Retry** -- per-agent retry (max 2) for transient failures or malformed output
2. **Checkpoint** -- save `impl-tmp/checkpoint.json` before each phase; rollback and re-dispatch on phase failure
3. **Graceful degradation** -- if one parallel agent fails, continue with successful ones; retry only the failed agent

## State Management

All state lives in `impl-tmp/`:
```
impl-tmp/
  manifest.json          # Phase tracking
  checkpoint.json        # Rollback state (saved before each phase)
  code-spec.md           # Phase 1 output
  test-plan.md           # Phase 1 output
  refactor-suggestions.md
  refactor-review-*.md
  todo.md                # Phase 4 review issues
```

`checkpoint.json` schema: `{"phase":<N>,"manifest":<snapshot>,"files":[<list of modified files>]}`

Agents write to unique files -- no merge conflicts. Orchestrator context stays lean: read summaries, not full artifacts.
