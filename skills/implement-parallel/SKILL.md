---
name: implement-parallel
description: Use when dispatched by implement-orchestrator to implement a single plan step with parallel coders, or when you need to implement code and tests from a step specification simultaneously
---

# Implement Parallel

Dispatch two parallel coding agents (Impl Coder + Test Coder) to implement a single plan step. Each agent reads the step specification and writes to naturally separate file paths -- no worktrees needed.

## When to Use

- Dispatched by implement-orchestrator for each plan step
- Manually invoked when you have a step specification ready and want parallel implementation

## Prerequisites

- A step specification is available (from `$IMPL_TMP/current-step.md`, `$IMPL_TMP/code-spec.md`, or orchestrator context)
- Optionally, `$IMPL_TMP/test-plan.md` exists for test guidance

## The Process

### 1. Dispatch Parallel Agents

Launch 2 subagents simultaneously via the Task tool:

| Agent | Reads | Writes | Focus |
|-------|-------|--------|-------|
| **Impl Coder** | Step spec / `$IMPL_TMP/code-spec.md` | Source files per spec | Production code |
| **Test Coder** | Step spec / `$IMPL_TMP/test-plan.md` | Test files per plan | Test code |

No worktrees required -- implementation files and test files are naturally separate paths.

### 2. Monitor and Handle Errors

If one agent fails:
1. Let the successful agent continue
2. Retry the failed agent (max 2 retries)
3. If still failing after retries, report the failure with error details and continue with the successful agent's output

### 3. Collect Results

When both agents complete, gather their reports:
- Files created/modified by each agent
- Any deviations from spec
- Test results from the test coder

### 4. Return to Orchestrator

Return the file list and status to the orchestrator. Do NOT commit -- the orchestrator handles commits after the simplify skill runs.

## Quick Reference

| Step | Action | Output |
|------|--------|--------|
| 1 | Dispatch Impl Coder + Test Coder in parallel | Two running agents |
| 2 | Handle errors (retry max 2) | Recovered or reported failures |
| 3 | Collect reports | File lists, deviations, test results |
| 4 | Return to orchestrator | Status and file lists |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using worktrees for file separation | Unnecessary -- source and test files have different paths |
| Blocking on one agent's failure | Let the other continue; retry the failed one |
| Retrying indefinitely | Cap retries at 2; report and move on |
| Committing directly | Don't commit -- orchestrator commits after simplify |
| Implementing multiple steps at once | Implement only the current step |
| Storing temp files in repo | Use `$IMPL_TMP` (outside repo) for all temporary artifacts |
