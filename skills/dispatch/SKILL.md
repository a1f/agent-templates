---
name: dispatch
description: Use when the user wants to start the unblocked PRs from a design doc, issue, or artifact in parallel — one tmux window, worktree, and coding agent per PR — or invokes /dispatch.
argument-hint: "<issue ref, artifact, or design doc> [--session NAME] [--dry-run]"
allowed-tools: Read, Write, Bash, Grep, Glob
---

# dispatch

Take the work that is **ready to start** in a plan and fan it out: one tmux window per
PR, each in its own worktree, each running a coding agent on `/make-pr <ref> <PR#>`.

```
/dispatch <issue ref | artifact | design doc> [--session NAME] [--dry-run]

  1. Find the unblocked PRs
  2. Show the table, wait for approval   (gate)
  3. Write the plan
  4. Fan out — one window per PR
```

You own step 1 (judgement: what is actually ready). The script owns steps 2–4 of the
mechanics (worktree, branch, window, launch) so they are deterministic and repeatable.

## Phase 1 — Find the unblocked PRs

Read the source the user named:

- **Issue** (`#N`, `123`, or a URL) — `gh issue view <N> --json title,body -q .body`.
- **File** — read it. **Artifact URL** — fetch it.
- Nothing given? Scan the conversation for the last `PRD published: ... (issue #N)` or
  a plan the user just approved. Confirm the number with the user before proceeding.

Find the PR rows (a `## PR breakdown` section from `/pr-breakdown` has them as
`| PR | What | LOC | Done when |`). If the source has no PR-level breakdown, **stop**
and point the user at `/pr-breakdown` — do not invent one.

Then decide which rows are **ready to start**:

| Signal | Where it comes from |
|--------|---------------------|
| Dependencies satisfied | the plan's own ordering and parallelism notes (`*n.1 ∥ n.2 (independent)*` = no dependency between them; otherwise later rows in a slice wait on earlier ones) |
| Not already done | `gh pr list --state all --search "<PR#>"` — skip rows with a merged or open PR |
| Not already started | `git branch -a` and `git worktree list` — skip rows that already have a branch or worktree |

A row is ready when its dependencies are **merged** and nothing is already in flight for
it. When the plan marks a status column explicitly, trust it, but still check for an
in-flight branch or PR so a half-finished run does not hand out the same row twice.

Give each ready row a short kebab-case **slug** derived from its *What* (`^[a-z0-9][a-z0-9-]*$`,
2–4 words, e.g. `evidence-schema`). The slug names the branch, the worktree directory,
and the window, so keep it short and distinct.

## Phase 2 — Approve (gate)

Show the table in chat and **wait for approval or edits**. Never dispatch unasked —
each row spends real tokens.

```markdown
| PR | What | Slug | Why it's ready |
|----|------|------|----------------|
| 1.5 | Evidence handoff schema | evidence-schema | 1.4 merged (#138) |
| 1.6 | Vale prose gate | vale-gate | independent of 1.5 |

Blocked, not dispatching: 1.7 (waits on 1.6), 2.1 (waits on slice 1)
```

State what you are **not** dispatching and why — a silently dropped row reads as
"everything is covered" when it isn't.

## Phase 3 — Write the plan

Write the approved rows to a plan file (use a scratch path, not the repo):

```json
{
  "ref": "#135",
  "base": "origin/main",
  "items": [
    { "pr": "1.5", "slug": "evidence-schema" },
    { "pr": "1.6", "slug": "vale-gate" }
  ]
}
```

- `ref` — what the child agent works from, passed through to `/make-pr <ref> <PR#>`.
  An issue (`#135`), a path, or a URL. A row may override it with its own `ref`.
- `base` — optional, defaults to `origin/main`. Every worktree branches fresh from it,
  so run `git fetch origin` first if main has moved.
- `session` — optional; the current tmux session is used when absent.

Fields are charset-checked (slug, PR id, ref, base, session): the plan becomes a shell
command, and a rejected plan is a typo caught early. Fix and rewrite rather than
working around a rejection.

## Phase 4 — Fan out

```bash
python3 ~/.claude/at/scripts/dispatch.py --plan <plan.json> [--session NAME] [--dry-run]
```

Stdlib only — no `uv`, no dependencies. Run it from **inside the target repository**;
it anchors worktrees at that repo's main checkout even when called from a worktree.

Per row it creates the worktree `<repo>/.claude/worktrees/<slug>` on a new branch
`worktree-<slug>`, opens a tmux window `pr-<PR#>` already `cd`'d into it, and types
`claude "/make-pr <ref> <PR#>"` there, then Enter.

- `--dry-run` prints every git/tmux command and changes nothing. Use it when the user
  is unsure, or when a plan is large.
- `--session NAME` targets a session other than the current one. Outside tmux this is
  required.
- `--agent` selects the coding agent; `claude` is the only one wired today.

Exit codes: `0` all windows up, `1` at least one failed (each row is isolated — one
failure does not stop the rest), `2` the plan or environment was rejected before
anything ran.

## Phase 5 — Report

Say what is now running and how to reach it — window names, worktree paths, and any row
that failed with its reason. Note that each window's agent stops at Claude Code's
first-run **"Do you trust this folder?"** prompt (every worktree is a new directory);
the user presses Enter once per window to start it.

Do not follow the dispatched work yourself. Those agents run independently; this skill
is done once the windows are up and reported.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Dispatching without the approval gate | Always show the table and wait |
| Inventing PR rows the plan does not have | Stop; send the user to `/pr-breakdown` |
| Dispatching a row that already has a branch or open PR | Check `git branch -a` and `gh pr list` in Phase 1 |
| Running the script from outside the target repo | `cd` to the repo first — the repo it is run in is the repo it branches |
| Long or duplicated slugs | 2–4 kebab-case words, unique within the plan |
| Babysitting the spawned windows | They are independent; report and stop |
