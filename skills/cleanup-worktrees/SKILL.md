---
name: cleanup-worktrees
description: Use when the user wants to remove stale agent worktrees under .claude/worktrees/ in the current repo, or invokes /cleanup-worktrees. Safely skips worktrees with uncommitted changes unless --force is passed.
---

# Cleanup Agent Worktrees

Remove stale per-agent git worktrees under `.claude/worktrees/agent-*/` in the current repo.

These worktrees are created by the Claude Code harness when a subagent is launched with
`isolation: "worktree"` and the subagent makes file changes (the harness only auto-cleans
worktrees whose agent wrote nothing). Without a cleanup step, each run leaves a full repo
checkout behind — observed consuming 9.7 GB per worktree in one repo (175 GB across 18
stale worktrees).

This skill is the **interrupt-recovery path**: markdown skills cannot install trap
handlers, so if an orchestrator is interrupted (Ctrl+C, crash) before its final cleanup
runs, re-invoke `/cleanup-worktrees` manually to reclaim disk space.

```
/cleanup-worktrees [--force] [--dry-run]
```

## Arguments

| Arg | Default | Effect |
|-----|---------|--------|
| `--force` | off | Remove worktrees even if they contain uncommitted changes or untracked files (destructive; opt-in) |
| `--dry-run` | off | Print what would be removed, make no changes |

## Execution

### 1. Resolve paths

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
WORKTREES_DIR="$REPO_ROOT/.claude/worktrees"
```

If `$WORKTREES_DIR` does not exist, print `nothing to clean` and exit 0.

### 2. Enumerate candidates

Match only `$WORKTREES_DIR/agent-*/` — do not touch sibling subdirectories the user may
have created for other purposes.

```bash
shopt -s nullglob
candidates=("$WORKTREES_DIR"/agent-*/)
```

If the list is empty, print `nothing to clean` and exit 0.

### 3. Safety guard

For each candidate, check for uncommitted changes or untracked files:

```bash
if [[ -n "$(git -C "$dir" status --porcelain 2>/dev/null)" ]]; then
  # Has uncommitted work — skip unless --force
  ...
fi
```

Skip any dir with a non-empty status unless `--force` is passed. A skipped dir is reported
in the summary with its reason.

Rationale: in-flight agent work that hasn't been committed back is the one thing worth
preserving for debugging. The user can opt in with `--force` once they've inspected.

### 4. Remove each candidate

For each non-skipped candidate:

```bash
# Primary path: unregister from git and remove the directory
git -C "$REPO_ROOT" worktree remove "$dir" --force || rm -rf "$dir"
```

If `git worktree remove` fails (e.g. the worktree registration is already detached), fall
back to `rm -rf` on the directory. Either way the directory is gone.

With `--dry-run`, print the command that would run and skip the actual removal.

### 5. Prune worktree registrations

After all removals:

```bash
git -C "$REPO_ROOT" worktree prune
```

This drops any dangling registrations in `.git/worktrees/` left over from previous
incomplete cleanups.

### 6. Print summary

```
Removed: <N> worktrees
Skipped: <M> worktrees (uncommitted changes — pass --force to override)
Freed:   <human-readable size>
```

Include the per-entry paths so the user can audit.

## When to Invoke

- **As a final step of an orchestrator pipeline** (`implement-orchestrator`,
  `implement-till-merge`) — mandatory, runs even on the error path.
- **Manually after an interrupt** — Ctrl+C'd a long-running pipeline? Run this to reclaim
  the disk space the harness left behind.
- **Periodically** — if you regularly use skills that launch isolated agents, run it as
  housekeeping.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Using `--force` by default in pipelines | Never pass `--force` from an orchestrator — it silently destroys uncommitted agent work. Only the user should opt in. |
| Targeting the user-global `~/.claude/skills/cleanup/` | That skill is for sibling worktrees in `~/dev/<repo>-<branch>/`. This skill is for per-agent worktrees *inside* a single repo. Different scope, both needed. |
| Removing `$WORKTREES_DIR` itself | Only remove `agent-*/` children. The parent dir is harmless and may be recreated by future agents. |
| Skipping `worktree prune` | Git keeps dangling registrations in `.git/worktrees/` even after the directory is gone. Always prune. |
