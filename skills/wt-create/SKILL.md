---
name: wt-create
description: Use when the user wants to create a git worktree for parallel work, or invokes /wt-create. Creates a worktree, branch, and prints tmux/cd commands.
---

# Create Worktree

Create a git worktree for working on a task in parallel. Outputs the branch name, tmux session command, and cd path so the user can immediately start working.

```
/create-worktree <branch-name> [--base=branch]
```

## Arguments

| Arg | Default | Example |
|-----|---------|---------|
| `branch-name` | Required | `fix-tag-names` |
| `--base=branch` | Default branch | `--base=develop` |

## Execution

### 1. Resolve paths

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
REPO_NAME=$(basename "$REPO_ROOT")
BRANCH_NAME="$ARG_BRANCH_NAME"
BASE_BRANCH="${ARG_BASE:-$(gh repo view --json defaultBranchRef -q '.defaultBranchRef.name' 2>/dev/null || echo 'main')}"
WORKTREE_PATH="$(dirname "$REPO_ROOT")/${REPO_NAME}-${BRANCH_NAME}"
```

### 2. Fetch latest base

```bash
git fetch origin "$BASE_BRANCH"
```

### 3. Create worktree

```bash
git worktree add -b "$BRANCH_NAME" "$WORKTREE_PATH" "origin/$BASE_BRANCH"
```

If the branch already exists:
```bash
git worktree add "$WORKTREE_PATH" "$BRANCH_NAME"
```

### 4. Print output

**Always print all of this to the console so the user can copy-paste:**

```
Worktree created:

Branch: <BRANCH_NAME>
Path:   <WORKTREE_PATH>

# Start a tmux session:
S=<REPO_NAME>-<BRANCH_NAME>; tmux new-session -s $S || tmux attach -t $S

# Navigate to worktree:
cd <WORKTREE_PATH>
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Not printing the tmux command | ALWAYS print the tmux and cd commands — the user needs them to start working |
| Creating worktree in the repo directory | Worktree goes in the parent directory alongside the main repo |
| Not fetching latest base first | Fetch before creating to ensure the worktree starts from latest |
