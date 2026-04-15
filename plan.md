# Code Plan: cleanup-worktrees skill + worktree-isolation policy in orchestrator pipeline

**Size:** medium

## Context

The bug in `~/implement_issue.md` reports that `.claude/worktrees/agent-<hash>/` directories
accumulate indefinitely (18 dirs × 9.7 GB = 175 GB in one repo), filling the user's disk.

Investigation findings:

- `.claude/worktrees/agent-*/` is created by the **Claude Code harness** when an agent is
  launched with `isolation: "worktree"` (Agent tool parameter or declarative agent field).
  The harness auto-cleans only when the agent made no file changes; if it did make changes,
  the worktree path + branch are returned and the caller is responsible for cleanup.
- **None of the current skills in this repo pass `isolation: "worktree"`** — so this repo
  is not the proximate cause, but is the right place to ship the fix because:
  1. The bug spec names `implement-orchestrator`, `implement-parallel`, `implement-till-merge`
     as affected skills and asks the fix to land there.
  2. The user's existing `~/.claude/skills/cleanup/SKILL.md` targets top-level sibling
     worktrees (e.g. `~/dev/<repo>-<branch>`), **not** `.claude/worktrees/agent-*/` inside
     a repo — that gap is called out explicitly in the bug's "Related Context".
  3. Any future edit to these skills that adds `isolation: "worktree"` needs a guaranteed
     cleanup path ready to call.

## Files to Modify

- `skills/implement-orchestrator/SKILL.md` — add "Worktree Isolation Policy" section and a
  final "Cleanup agent worktrees" pipeline step that dispatches `cleanup-worktrees`.
  Reason: this is the orchestrator that the bug explicitly names.

- `skills/implement-parallel/SKILL.md` — strengthen the existing "No worktrees required"
  note by adding a one-line policy pointer: if a future change introduces isolation, it
  must invoke `cleanup-worktrees` before returning to the orchestrator.
  Reason: this is the skill that dispatches the parallel coder agents, and is the likely
  place a future contributor would add `isolation: "worktree"`.

- `skills/implement-till-merge/SKILL.md` — add a final "Cleanup" step that invokes
  `cleanup-worktrees` after the merge-ready gate.
  Reason: end-to-end pipeline; guarantees cleanup even if an earlier phase spawned worktrees
  via some transitive path.

## New Files to Create

- `skills/cleanup-worktrees/SKILL.md` — new user-invocable skill (`/cleanup-worktrees`)
  that removes stale `.claude/worktrees/agent-*/` entries in the current repo.

  Behavior:
  1. Resolve `REPO_ROOT=$(git rev-parse --show-toplevel)`.
  2. If `$REPO_ROOT/.claude/worktrees/` does not exist → print "nothing to clean" and exit 0.
  3. Enumerate `$REPO_ROOT/.claude/worktrees/agent-*/` (only that glob — do not touch
     sibling subdirs the user may have created).
  4. Safety guard: if any candidate dir contains **uncommitted changes** or **untracked
     files**, skip it and warn — this preserves in-flight agent work that hasn't been merged.
     Implemented as `git -C <dir> status --porcelain` returning non-empty.
  5. For each remaining dir: run `git worktree remove <dir> --force` from `$REPO_ROOT`.
     If that fails (already-detached worktree), fall back to `rm -rf <dir>`.
  6. Run `git -C $REPO_ROOT worktree prune`.
  7. Print a summary: N removed, M skipped (with reasons).

  Flags:
  - `--force` — bypass the uncommitted-changes guard (explicit opt-in).
  - `--dry-run` — print what would be removed, make no changes.

## Functions/Types to Extract

None. Skills are markdown instruction files — no code extraction needed.

## Reuse Opportunities

- The existing `~/.claude/skills/cleanup/SKILL.md` handles **sibling** worktrees in `~/dev/`
  (e.g. `~/dev/<repo>-<branch>`). It does **not** handle `.claude/worktrees/agent-*/` inside
  a repo. Do **not** modify that user-global skill — the new `cleanup-worktrees` skill lives
  in this repo (project-level plugin) and has a narrower, repo-scoped responsibility. The
  existing skill's docstring explicitly cites this gap.
- `skills/wt-create/SKILL.md` already has the `git worktree add` idiom — reuse the same
  shell-command style (bash code blocks with `$VAR` expansions) so the new skill reads
  consistently with the rest of the repo.
- Agent tool description already documents the isolation/cleanup contract — reference it
  in the Worktree Isolation Policy section rather than re-explaining it.

## Dependency Direction

- `cleanup-worktrees` (leaf) → [no skill deps]. Stable: shells out to `git worktree` only.
- `implement-orchestrator` → `cleanup-worktrees` (adds one Skill invocation in its final step).
- `implement-till-merge` → `cleanup-worktrees` (adds one final-step invocation).
- `implement-parallel` → [no new dep] (documentation-only change).

All new edges point from more-volatile orchestrators toward the stable leaf cleanup skill.
Direction is correct.

## Naming Decisions

- **`cleanup-worktrees`** (not `clean-worktrees`, not `agent-worktree-cleanup`):
  - Verb-noun form matches existing skill names (`clean-code-planner`, `latest-update`,
    `pr-make`).
  - `cleanup` echoes the user's existing sibling-worktree skill name, signaling "same family
    of operation, different scope" rather than introducing a new verb.
  - Plural `worktrees` because it processes many in one call.
- **"Worktree Isolation Policy"** (section title in `implement-orchestrator`): names the
  concept the harness calls `isolation: "worktree"`, so contributors searching for that
  flag find the policy.

## Data Flow

Not applicable — no data types are being modified. Skill invocations are independent and
each is idempotent with respect to the filesystem.

## Acceptance Criteria Mapping

| Bug spec criterion | How this plan addresses it |
|---|---|
| Running orchestrator to completion leaves zero entries in `.claude/worktrees/` | Final step of `implement-orchestrator` invokes `cleanup-worktrees`. With current skills (which don't use isolation), this is a no-op; with future changes it's load-bearing. |
| Agent failure still cleans up | `implement-orchestrator` final step runs even in the error path (documented as mandatory, like the existing `$IMPL_TMP` cleanup). `cleanup-worktrees` itself skips dirs with uncommitted changes so failed-but-in-progress work is preserved for debugging. |
| Ctrl+C interrupt best-effort cleanup | Markdown skills cannot install trap handlers. Closest safe pattern: user re-runs `/cleanup-worktrees` manually. Call this out explicitly in the new skill's docstring so the user knows it's the recovery path. |
| Does not auto-delete pre-existing worktrees user wants to keep | The uncommitted-changes guard in `cleanup-worktrees`. Plus `--dry-run` for user inspection before committing. |
| Manual `cleanup-worktrees` subcommand or skill | The new `skills/cleanup-worktrees/SKILL.md`. |

## Explicit Non-Goals

- Modifying the user's global `~/.claude/skills/cleanup/SKILL.md`. It has a different scope
  (sibling worktrees in `~/dev/`) and is user-owned.
- Adding `isolation: "worktree"` to any existing skill. The current design works without it.
- Installing shell trap handlers. Skills are markdown; traps belong to the harness.
- Touching `make-pr` / `pr-make` / `pr-babysit`. These don't spawn agent worktrees.
  The bug spec lists them under "affected skills" as a precaution, but there's no code path
  in them that creates `.claude/worktrees/agent-*/`. Adding cleanup calls there would be
  defensive programming against a non-issue — YAGNI.
