---
name: plan-till-merge
description: Use when the user wants to plan, implement, and take it all the way to a merge-ready PR, or invokes /plan-till-merge.
---

# Plan Till Merge

Plan with clean code principles, implement the plan, create a PR, and babysit it through review/CI until ready to merge. Runs all phases directly in sequence — no nested skill dispatch.

```
/plan-till-merge [description or context] [make-pr args...] [--interval 3m] [--max-rounds 5]

Phase 1: /clean-code-planner → plan.md
Phase 2: /implement-orchestrator → committed code
Phase 3: /issue-make → GitHub issue with artifacts
Phase 4: /make-pr → gates + review + push + create PR
Phase 5: /pr-babysit → poll until [READY TO MERGE]
```

## Arguments

All optional. Parsed from the user's message:

| Arg | Phase | Default | Example |
|-----|-------|---------|---------|
| `--issue=N` | 3, 4 | Auto-detect | `--issue=42` |
| `--reviewers=u1,u2` | 4 | Auto-detect | `--reviewers=alice` |
| `--no-reviewers` | 4 | Reviewers added | `--no-reviewers` |
| `--title="..."` | 3, 4 | From plan | `--title="Add auth"` |
| `--base=branch` | 4 | Default branch | `--base=develop` |
| `--draft` | 4 | Not draft | `--draft` |
| `--interval=DURATION` | 5 | `3m` | `--interval=5m` |
| `--max-rounds=N` | 5 | `5` | `--max-rounds=10` |

## Checkpoint/Resume

Before starting, check for existing state:

```bash
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD | tr '/' '-')
STATE_FILE="${TMPDIR:-/tmp}/claude-impl/${REPO_NAME}/${BRANCH_NAME}/plan-till-merge-state.json"
```

If `STATE_FILE` exists, read it:
```json
{"phase": 2, "issue_number": 42, "pr_number": null, "branch": "feat/my-feature"}
```

If state exists and the branch matches, ask the user: "Phases 1-N already completed. Resume from Phase N+1?" If yes, skip completed phases. If no (or branch mismatch), start fresh.

After each phase completes, update the state file with the current phase number and any IDs (issue number, PR number).

Clean up the state file after Phase 5 completes.

## Phase 1: Plan

Use the Skill tool to invoke `clean-code-planner`. The input comes from the user's description, `improvement.md`, `plan.md`, or any context they provided.

Wait for it to complete. It produces `plan.md`.

## Phase 2: Implement

Use the Skill tool to invoke `implement-orchestrator`. It reads `plan.md` and implements each step with commit-per-step.

Wait for it to complete. All steps should be committed.

## Phase 3: Issue

Use the Skill tool to invoke `issue-make` with:
- `--title` derived from `plan.md` first heading
- `--issue=N` if the user provided one
- `--attach-md` (default true — attaches planning artifacts)

This creates/updates the GitHub issue and attaches planning `.md` files as a gist.

## Phase 4: PR

Use the Skill tool to invoke `make-pr` with:
- `--issue=N` from Phase 3 result
- `--reviewers`, `--no-reviewers`, `--title`, `--base`, `--draft`, `--no-agent-review` if the user provided them

This runs gates, quick review, `/review-and-fix`, pushes, and creates the PR. (`/make-pr` invokes `/review-and-fix` internally as Phase 2.5.)

## Phase 5: Babysit

Use the Skill tool to invoke `pr-babysit` with:
- `--interval` and `--max-rounds` if the user provided them

This polls until `[READY TO MERGE]` or `[MAX ROUNDS EXHAUSTED]`.

## Error Handling

If any phase fails:
- **Phase 1 (Plan):** Stop and report — the user needs to clarify requirements
- **Phase 2 (Implement):** Stop and report — committed steps are safe checkpoints
- **Phase 3 (Issue):** Warn but continue — issue creation is best-effort
- **Phase 4 (PR):** Stop and report — gate failures or push errors need attention
- **Phase 5 (Babysit):** Report final status — `[READY TO MERGE]` or `[MAX ROUNDS EXHAUSTED]`

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Starting Phase 2 before Phase 1 completes | Each phase depends on the previous one completing |
| Skipping Phase 3 (issue-make) | ALWAYS create/update the issue — it provides traceability |
| Nesting skill calls (skill → skill → skill) | Each phase invokes its skill directly — no intermediary skills |
| Dropping user arguments | Forward each argument to the correct phase |
