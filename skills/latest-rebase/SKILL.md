---
name: latest-rebase
description: Use when the user invokes /latest-rebase or says "rebase on latest main". Rebases current branch onto latest remote main.
---

# Latest Rebase

Rebase the current branch onto the latest remote main. Handles stashing, conflict detection, and force-push.

## Execution

### 1. Fetch and rebase

```bash
git fetch origin main
```

If there are unstaged changes, stash them first:
```bash
git stash
git rebase origin/main
git stash pop
```

Otherwise:
```bash
git rebase origin/main
```

### 2. Check result

Check if commits are ahead of main:
```bash
git log origin/main..HEAD --oneline
```

- If no commits ahead: branch was already merged. Switch to main, pull, delete branch locally and remotely. Run validate and install.
- If commits ahead: rebase succeeded with work remaining. Ask if the user wants to force-push (`git push --force-with-lease`).

### 3. If rebase had conflicts

If rebase fails with conflicts:
- Show which files have conflicts
- Ask the user how to proceed (resolve, abort, or skip)
- Do NOT automatically resolve conflicts

### 4. Validate and install

```bash
./validate.sh
./install.sh --non-interactive --all
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Force-pushing without asking | Always ask before `--force-with-lease` |
| Auto-resolving conflicts | Show conflicts and ask the user |
| Forgetting to validate after rebase | ALWAYS run validate and install |
