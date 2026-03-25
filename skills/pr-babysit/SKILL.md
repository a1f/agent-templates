---
name: pr-babysit
description: Use when the user wants to babysit a PR through the review/CI cycle, or invokes /pr-babysit. Polls for new review comments and CI failures, fixes them, resolves merge conflicts, and loops until the PR is ready to merge.
---

# PR Babysit

Automate the post-PR feedback loop. Polls for new review comments, fixes them, checks CI, resolves merge conflicts, pushes, and repeats until the PR is clean or max rounds are exhausted.

```
/pr-babysit [--interval 3m] [--max-rounds 5]

Loop:
  1. Fetch PR comments & reviews + CI status + mergeable status (parallel)
  2. Filter for unresolved/new comments since last check
  3. Fix all actionable comments, then run quick gates once
  4. Reply to question comments (parallel)
  5. If CI failing → read logs, fix failures
  6. If conflicts → rebase/merge main and resolve conflicts
  7. If changes were made → commit & push, reset idle counter
  8. If nothing left to fix AND CI green AND no conflicts → [READY TO MERGE]
  9. Otherwise → wait interval, repeat
```

## Prerequisites

The `gh` CLI must be authenticated with `repo` scope. The `jq` command must be available.

## Arguments

Parse arguments from the user's message. All are optional:

| Arg | Default | Example |
|-----|---------|---------|
| `--interval=DURATION` | `3m` | `--interval=5m` |
| `--max-rounds=N` | `5` | `--max-rounds=10` |

## Phase 0: Setup

### 0a. Detect Current PR and Repo Info

Fetch PR data and repo info in parallel:

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Parallel: PR info + repo info
PR_JSON=$(gh pr view --json number,url,baseRefName,mergeable,mergeStateStatus,createdAt)
REPO_INFO=$(gh repo view --json owner,name)
```

If no PR exists for the current branch, stop and tell the user to create one first (suggest `/make-pr` or `/pr-make`).

Extract:
```bash
PR_NUMBER=$(echo "$PR_JSON" | jq -r '.number')
PR_URL=$(echo "$PR_JSON" | jq -r '.url')
BASE_BRANCH=$(echo "$PR_JSON" | jq -r '.baseRefName')
PR_CREATED_AT=$(echo "$PR_JSON" | jq -r '.createdAt')
OWNER=$(echo "$REPO_INFO" | jq -r '.owner.login')
REPO=$(echo "$REPO_INFO" | jq -r '.name')
```

### 0b. Initialize State

```
IDLE_ROUNDS_REMAINING = max-rounds (default 5)
MAX_TOTAL_ITERATIONS = max-rounds * 3    # hard cap to prevent infinite loops
TOTAL_ITERATIONS = 0
INTERVAL = interval (default 3m)
LAST_CHECKED = PR_CREATED_AT             # first pass processes all existing comments
TOTAL_WAIT_MINUTES = 0
CONSECUTIVE_READY_COUNT = 0              # must reach 2 before declaring ready
```

Two counters prevent infinite loops:
- `IDLE_ROUNDS_REMAINING` resets when progress is made (commit & push). Exhaustion means the PR stalled.
- `MAX_TOTAL_ITERATIONS` never resets. Exhaustion means the skill has been running too long regardless of progress.

## Phase 1: The Loop

Each iteration runs these phases in order. Evaluate exit conditions at the end.

### 1a. Check PR State

Before doing any work, verify the PR is still open:

```bash
PR_STATE=$(gh pr view "$PR_NUMBER" --json state -q '.state')
```

If `PR_STATE` is `MERGED` or `CLOSED`, print the PR URL and exit — no further action needed.

### 1b. Fetch New Data (Parallel)

Kick off all data fetches in parallel at the start of each iteration:

```bash
# All three in parallel:

# 1. Review comments (inline code comments)
COMMENTS=$(gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments" \
  --paginate \
  -q '[.[] | select(.created_at > "'"$LAST_CHECKED"'") | {id, path, line, body, user: .user.login}]')

# 2. Review bodies (top-level review comments)
REVIEWS=$(gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" \
  --paginate \
  -q '[.[] | select(.submitted_at > "'"$LAST_CHECKED"'" and .body != "") | {id, body, user: .user.login, state}]')

# 3. CI status + mergeable status
CHECKS=$(gh pr checks "$PR_NUMBER" --json name,state,conclusion,detailsUrl)
MERGEABLE=$(gh pr view "$PR_NUMBER" --json mergeable,mergeStateStatus)
```

Update `LAST_CHECKED` to current UTC timestamp after fetching.

### 1c. Categorize Comments

For each new comment (from both inline comments and review bodies), categorize:

1. **Actionable code change** — requests a specific code modification (e.g., "rename this variable", "add error handling here", "this should use X instead of Y")
2. **Question** — asks something that needs a reply (e.g., "why did you choose this approach?", "is this tested?")
3. **Informational / FYI** — no action needed (e.g., coverage reports, bot status messages, "LGTM", acknowledgements)

Skip informational comments entirely.

### 1d. Fix All Actionable Comments

Process all actionable comments, then run gates once:

1. For each actionable comment:
   - Read the referenced file at the referenced line
   - Understand the reviewer's request in context
   - Apply the fix
2. After **all** comment fixes are applied, run quick gates once:
   ```bash
   # Run format + lint gates from gates.json if it exists
   if [ -f .claude/gates.json ]; then
     SETUP=$(jq -r '.setup // empty' .claude/gates.json)
     [ -n "$SETUP" ] && eval "$SETUP"
     # Run all gates that have a fix command (typically format and lint)
     for fix_cmd in $(jq -r '.gates[] | select(.fix != null) | .fix' .claude/gates.json); do
       eval "$fix_cmd"
     done
   fi
   ```

### 1e. Reply to Questions

For each question comment, reply with a concise answer. Fire all replies in parallel.

For **inline review comments**, reply in the review thread:
```bash
gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments/$COMMENT_ID/replies" \
  -f body="$REPLY_TEXT"
```

For **top-level review bodies**, reply as a PR comment:
```bash
gh pr comment "$PR_NUMBER" --body "$REPLY_TEXT"
```

Base replies on actual code and commit history — don't make things up.

### 1f. Fix CI Failures

From the checks data fetched in 1b, categorize each check:
- **Passing** (`conclusion: "SUCCESS"` or `conclusion: "NEUTRAL"`) — no action, terminal state
- **Failing** (`conclusion: "FAILURE"`) — needs fixing, terminal state
- **Still running** (`state: "PENDING"`, `state: "QUEUED"`, or `state: "IN_PROGRESS"`) — not terminal, must wait. This includes external tools like Cursor Bugbot, Noa Analysis, etc. — treat them the same as any other check

If any checks are failing:

1. Extract the run ID from `detailsUrl`
2. Fetch failure logs:
   ```bash
   gh run view "$RUN_ID" --log-failed 2>/dev/null | tail -100
   ```
3. Analyze the failure and apply fixes
4. If the failure is a flaky test or infrastructure issue (not caused by code), note it but don't modify code

### 1g. Resolve Merge Conflicts

From the mergeable data fetched in 1b, check if `mergeable` is `"CONFLICTING"` or `mergeStateStatus` is `"DIRTY"`.

If conflicts exist:

1. Fetch latest base branch:
   ```bash
   git fetch origin "$BASE_BRANCH"
   ```

2. Attempt rebase:
   ```bash
   git rebase "origin/$BASE_BRANCH"
   ```

3. If rebase has conflicts:
   - If more than 3 files have conflicts, abort (`git rebase --abort`) and fall back to merge:
     ```bash
     git merge "origin/$BASE_BRANCH"
     ```
   - Otherwise, resolve each conflict by reading both sides and choosing the correct resolution
   - Continue: `git rebase --continue`

### 1h. Evaluate and Act

Increment `TOTAL_ITERATIONS`.

**If any changes were made** (code fixes, conflict resolution, CI fixes):
1. Stage all changes
2. Commit with a descriptive message:
   - Review fixes: `fix: address review feedback — <summary>`
   - CI fixes: `fix: resolve CI failures — <summary>`
   - Conflict resolution: `fix: resolve merge conflicts with <base_branch>`
3. Push:
   ```bash
   git push
   ```
   If push fails after rebase (diverged history), use:
   ```bash
   git push --force-with-lease
   ```
4. **Reset `IDLE_ROUNDS_REMAINING` to `max-rounds`** — progress was made
5. **Reset `CONSECUTIVE_READY_COUNT` to 0** — changes invalidate any previous ready verdict

**If no changes were needed** AND **every** check has reached a terminal state (SUCCESS, NEUTRAL, or FAILURE — no PENDING, QUEUED, or IN_PROGRESS) AND all required checks pass AND no conflicts:
→ Increment `CONSECUTIVE_READY_COUNT`
→ If `CONSECUTIVE_READY_COUNT >= 2`: print and exit:
```
[READY TO MERGE] <PR_URL>
```
→ If `CONSECUTIVE_READY_COUNT < 2`: **immediately** re-fetch all data (skip the wait) and re-check. This double-check avoids race conditions where checks or comments arrive between fetches, without adding unnecessary delay.

**If no changes were needed** but any check is still running (PENDING, QUEUED, IN_PROGRESS) or `mergeStateStatus` is UNSTABLE:
→ This is **not** ready — reset `CONSECUTIVE_READY_COUNT` to 0, decrement `IDLE_ROUNDS_REMAINING`, wait, and re-check next iteration. Do NOT declare `[READY TO MERGE]` while any check is still in progress, even if it's an external/non-required check.

**If no changes were needed** and all checks are terminal but some required checks failed with unfixable issues:
→ Reset `CONSECUTIVE_READY_COUNT` to 0, decrement `IDLE_ROUNDS_REMAINING`

### 1i. Check Exit Conditions

Check exit conditions before waiting:

**Hard cap reached** (`TOTAL_ITERATIONS >= MAX_TOTAL_ITERATIONS`):
→ Print and exit:
```
[MAX ROUNDS EXHAUSTED] waited for <TOTAL_WAIT_MINUTES> minutes. <PR_URL>
```

**Idle rounds exhausted** (`IDLE_ROUNDS_REMAINING <= 0`):
→ Print and exit:
```
[MAX ROUNDS EXHAUSTED] waited for <TOTAL_WAIT_MINUTES> minutes. <PR_URL>
```

Otherwise:
→ Wait `INTERVAL`
→ Add interval duration to `TOTAL_WAIT_MINUTES`
→ Continue to next iteration

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| No PR on current branch | Detect early and suggest `/make-pr` |
| Not checking if PR is still open | Check PR state at the top of every iteration |
| Fixing informational bot comments | Skip coverage reports, status bots, LGTM comments |
| Force-pushing without lease | Always use `--force-with-lease` after rebase, never `--force` |
| Not resetting idle counter | Reset `IDLE_ROUNDS_REMAINING` whenever changes are committed and pushed |
| No hard cap on total iterations | `MAX_TOTAL_ITERATIONS` prevents infinite loops even when progress keeps resetting the idle counter |
| Guessing answers to reviewer questions | Base replies on actual code and history — read the files |
| Running gates per-comment | Batch all comment fixes first, then run gates once |
| Modifying code for flaky test failures | Note flaky tests but don't change code unless it's a real bug |
| Declaring ready after one clean pass | Must get 2 consecutive ready verdicts to avoid race conditions |
| Waiting twice in one iteration | Wait happens in exactly one place: step 1i |
| Replying to top-level reviews via comment reply API | Top-level review bodies use `gh pr comment`, inline comments use the replies API |
