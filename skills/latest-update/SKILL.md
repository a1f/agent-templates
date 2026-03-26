---
name: latest-update
description: Use when the user invokes /latest-update or says "update to latest main". Pulls latest remote main, cleans up merged branches, validates, and installs.
---

# Latest Update

Update to the latest remote main. If on a feature branch, check if it's merged and clean up.

## Execution

### 1. Fetch latest main

```bash
git fetch origin main
```

### 2. Check current branch

If on a feature branch (not main):
- Check if commits are ahead of main: `git log origin/main..HEAD --oneline`
- If no commits ahead (already merged): switch to main, delete the branch locally and remotely
- If commits ahead: warn the user that the branch has unmerged work

If on main:
- `git pull origin main`

### 3. Validate and install

```bash
./validate.sh
./install.sh --non-interactive --all
```

### 4. Print status

Print current branch, latest commit, and validation result.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Deleting a branch with unmerged work | Only delete branches that are fully merged into main |
| Forgetting to validate after update | ALWAYS run validate and install |
