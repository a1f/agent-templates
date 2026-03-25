---
name: plan-till-merge
description: Use when the user wants to plan, implement, and take it all the way to a merge-ready PR, or invokes /plan-till-merge.
---

# Plan Till Merge

Plan with clean code principles, implement the plan, create a PR, and babysit it through review/CI until ready to merge.

```
/plan-till-merge [description or context] [make-pr args...] [--interval 3m] [--max-rounds 5]

  1. /clean-code-planner — create a plan with clean code principles
  2. /implement-till-merge — implement, create PR, babysit until ready to merge
```

## Execution

### Step 1: Create the Plan

Use the Skill tool to invoke `clean-code-planner`. The input comes from the user's description in the conversation or any context they've provided.

Wait for `/clean-code-planner` to complete. It will produce `plan.md`.

### Step 2: Implement Through to Merge

Use the Skill tool to invoke `implement-till-merge` with any PR-related and babysit-related arguments the user provided. It will read `plan.md` and execute the full pipeline.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Starting implementation before plan is done | /clean-code-planner must finish and save plan.md first |
| Skipping the planning phase | Always run /clean-code-planner — it ensures clean code principles |
