---
name: implement-parallel
description: Use when dispatched by implement-orchestrator to execute code-spec.md and test-plan.md with parallel coders, or when you need to implement code and tests from specifications simultaneously
---

# Implement Parallel

Dispatch two parallel coding agents (Impl Coder + Test Coder) to execute Phase 2 of the agentic pipeline. Each agent reads its spec from `impl-tmp/` and writes to naturally separate file paths -- no worktrees needed.

## When to Use

- Dispatched by implement-orchestrator as Phase 2
- Manually invoked when `impl-tmp/code-spec.md` and `impl-tmp/test-plan.md` both exist and you want parallel implementation

## Prerequisites

- `impl-tmp/code-spec.md` exists (output of plan-codebase)
- `impl-tmp/test-plan.md` exists (output of plan-tests)

## The Process

### 1. Dispatch Parallel Agents

Launch 2 subagents simultaneously via the Task tool:

| Agent | Reads | Writes | Prompt Template |
|-------|-------|--------|-----------------|
| **Impl Coder** | `impl-tmp/code-spec.md` | Source files per spec | `implementer-prompt.md` |
| **Test Coder** | `impl-tmp/test-plan.md` | Test files per plan | `test-coder-prompt.md` |

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

### 4. Update Manifest

Update `impl-tmp/manifest.json` with Phase 2 status:
```json
{"phase":2,"status":"complete","outputs":{"impl_files":["<list>"],"test_files":["<list>"]},"timestamp":"<ISO-8601>"}
```

### 5. Commit

Each agent commits its own work independently. If re-dispatched for fixes (Phase 3/4), agents commit fix iterations separately.

## Quick Reference

| Step | Action | Output |
|------|--------|--------|
| 1 | Dispatch Impl Coder + Test Coder in parallel | Two running agents |
| 2 | Handle errors (retry max 2) | Recovered or reported failures |
| 3 | Collect reports | File lists, deviations, test results |
| 4 | Update manifest.json | Phase 2 status recorded |
| 5 | Commit | Independent commits per agent |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using worktrees for file separation | Unnecessary -- source and test files have different paths |
| Blocking on one agent's failure | Let the other continue; retry the failed one |
| Retrying indefinitely | Cap retries at 2; report and move on |
| Skipping manifest update | Always update manifest.json even on partial failure |
| Merging agent commits | Each agent commits independently |
