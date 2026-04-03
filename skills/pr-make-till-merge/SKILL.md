---
name: pr-make-till-merge
description: Use when the user wants to create a PR and babysit it until ready to merge, or invokes /pr-make-till-merge.
---

# PR Make Till Merge

Create a PR and babysit it through the review/CI cycle until it's ready to merge.

```
/pr-make-till-merge [make-pr args...] [--interval 3m] [--max-rounds 5]

  1. /make-pr — create or update the PR (gates, review, /review-and-fix, push)
  2. /pr-babysit — poll for comments, fix CI, resolve conflicts, loop until ready
```

## Execution

### Step 1: Create/Update PR

Use the Skill tool to invoke `make-pr` with all arguments the user provided that match `/make-pr` arguments (`--issue`, `--reviewers`, `--title`, `--base`, `--draft`).

Wait for `/make-pr` to complete. If it fails (e.g., no commits, on base branch), stop and report the error.

### Step 2: Babysit PR

Use the Skill tool to invoke `pr-babysit` with any `--interval` and `--max-rounds` arguments the user provided.

`/pr-babysit` will loop until it prints `[READY TO MERGE]` or `[MAX ROUNDS EXHAUSTED]`.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running /pr-babysit before /make-pr completes | /make-pr must finish first — the PR must exist before babysitting |
| Dropping arguments | Forward make-pr args to make-pr, babysit args to pr-babysit |
