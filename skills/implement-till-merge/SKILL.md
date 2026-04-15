---
name: implement-till-merge
description: Use when the user wants to implement a plan and take it all the way to a merge-ready PR, or invokes /implement-till-merge.
---

# Implement Till Merge

Implement a plan, create a PR, and babysit it through review/CI until ready to merge.

```
/implement-till-merge [plan source] [make-pr args...] [--interval 3m] [--max-rounds 5]

  1. /implement-orchestrator — implement the plan step by step
  2. /pr-make-till-merge — create PR (/review-and-fix included) and babysit until ready to merge
```

## Execution

### Step 1: Implement the Plan

Use the Skill tool to invoke `implement-orchestrator`. The plan comes from the same sources `/implement-orchestrator` accepts: `plan.md`, conversation context, or any file the user points to.

Wait for `/implement-orchestrator` to complete. All steps should be committed.

### Step 2: PR and Babysit

Use the Skill tool to invoke `pr-make-till-merge` with any PR-related and babysit-related arguments the user provided.

### Step 3: Cleanup agent worktrees

After the PR reaches the merge-ready state (or the babysit loop exhausts its rounds),
invoke `cleanup-worktrees` to remove any stale `.claude/worktrees/agent-*/` entries the
pipeline may have left behind. Mandatory — runs even when Step 1 or Step 2 fails.

**REQUIRED SKILL:** cleanup-worktrees

Do not pass `--force` — the skill's uncommitted-changes guard preserves in-flight work.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Starting PR before implementation is done | /implement-orchestrator must finish and commit all steps first |
| Skipping implementation when plan exists | Always run /implement-orchestrator — it handles the plan |
| Skipping Step 3 cleanup on pipeline failure | Cleanup is mandatory on every exit path, including errors — agent worktrees accumulate otherwise |
