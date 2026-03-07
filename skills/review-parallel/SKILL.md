---
name: review-parallel
description: Use when dispatched by implement-orchestrator to run parallel code reviews with severity-based consensus, or when you need to coordinate multiple specialized code reviewers on a set of changes
---

# Review Parallel

Coordinate parallel independent code reviewers and apply severity-based consensus to produce an actionable `$IMPL_TMP/todo.md`. Runs as Phase 3 (Refactoring) and Phase 4 (Code Review) of the agentic pipeline.

## When to Use

- Dispatched by implement-orchestrator for Phase 3 or Phase 4
- Manually invoked when implementation is complete and you need multi-perspective review

## The Process

### Phase 3: Refactoring Review

Dispatch 3 parallel reviewers via the Task tool. Each reviewer uses `refactor-reviewer-prompt.md`:

| Reviewer | Focus |
|----------|-------|
| **Architecture** | Layer violations, dependency direction, module boundaries |
| **DRY** | Duplication, missed reuse, unnecessary abstractions |
| **Simplification** | Over-engineering, dead code, unnecessary complexity |

Each writes findings to `$IMPL_TMP/refactor-review-{name}.md`. Merge all results into `$IMPL_TMP/refactor-suggestions.md`. Return to orchestrator for re-dispatch of impl + test coders.

### Phase 4: Code Review Loop

Dispatch 5 fully independent reviewers via the Task tool. Each reviewer uses `code-reviewer-prompt.md`. **No reviewer sees another's output** -- aggregate mechanically.

| Reviewer | Focus |
|----------|-------|
| **Correctness** | Logic errors, edge cases, null handling, race conditions |
| **Spec Compliance** | plan.md vs actual code, missing/extra features |
| **Security** | OWASP top 10, input validation, injection, auth |
| **Maintainability** | Readability, DRY, complexity, testability |
| **Performance** | Algorithmic complexity, memory, I/O, allocations |

Each outputs: `[{file, line, issue, severity, category}]`

### Consensus

Apply severity-based rules from `consensus-rules.md`:

```
CRITICAL >=1 reviewer --> include
MAJOR    >=2 reviewers --> include
MINOR    >=3 reviewers --> include
LOW      --> logged only
```

Group issues by code location (within 5 lines = same location). Take highest severity per group.

### Actionability Check

Post-filter every surviving issue: **"Would a senior engineer change code based on this?"** Remove anything that fails this test.

### Output

Write `$IMPL_TMP/todo.md` with issues ordered by severity (desc), then vote count (desc).

### Loop Control

- **Early exit:** If `todo.md` has <2 issues, stop iterating
- **Max iterations:** 3. On iteration 3, escalate remaining critical issues to human
- **Diff-only on iterations 2-3:** Reviewers only examine the diff from the previous fix, not the full codebase

## Quick Reference

| Step | Action | Output |
|------|--------|--------|
| 1 | Dispatch 3 refactoring reviewers (Phase 3) | `$IMPL_TMP/refactor-suggestions.md` |
| 2 | Dispatch 5 code reviewers (Phase 4) | Raw issue lists |
| 3 | Apply consensus rules | Filtered issues |
| 4 | Actionability check | Final issues |
| 5 | Write todo.md | `$IMPL_TMP/todo.md` |
| 6 | Loop or exit | <2 issues or 3 iterations = stop |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Letting reviewers see each other's output | Keep fully independent -- sycophancy degrades quality |
| Skipping actionability check | Always apply "would a senior engineer act?" filter |
| Reviewing full codebase on iteration 2-3 | Use diff-only to reduce noise and tokens |
| Including LOW severity in todo.md | Log only -- never require action on LOW |
| Running more than 3 iterations | Hard cap at 3; escalate remaining critical issues |
