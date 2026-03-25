---
name: implement-till-merge
description: Use when the user wants to implement a plan and take it all the way to a merge-ready PR, or invokes /implement-till-merge.
---

# Implement Till Merge

Implement a plan, create a PR, and babysit it through review/CI until ready to merge.

```
/implement-till-merge [plan source] [make-pr args...] [--interval 3m] [--max-rounds 5]

  1. /implement-orchestrator — implement the plan step by step
  2. /pr-make-till-merge — create PR and babysit until ready to merge
```

## Execution

### Step 1: Implement the Plan

Use the Skill tool to invoke `implement-orchestrator`. The plan comes from the same sources `/implement-orchestrator` accepts: `plan.md`, conversation context, or any file the user points to.

Wait for `/implement-orchestrator` to complete. All steps should be committed.

### Step 2: PR and Babysit

Use the Skill tool to invoke `pr-make-till-merge` with any PR-related and babysit-related arguments the user provided.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Starting PR before implementation is done | /implement-orchestrator must finish and commit all steps first |
| Skipping implementation when plan exists | Always run /implement-orchestrator — it handles the plan |
