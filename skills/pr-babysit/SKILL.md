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
  2. Filter for unresolved/new comments since last check, split by human vs bot
  3. Human comments → trade-off assessment + user decision gate (AskUserQuestion or worksheet)
  4. Fix all actionable comments per gate decisions (bot: auto; human: per decision), run quick gates once
  5. Reply to question comments (bot: auto; human: only approved reply, in parallel)
  6. If CI failing → read logs, fix failures
  7. If conflicts → rebase/merge main and resolve conflicts
  8. If changes were made → commit & push, refresh the PR explainer, reset idle counter
  9. If nothing left to fix AND CI green AND no conflicts AND no undecided human comments → final explainer refresh, then [READY TO MERGE]
 10. Otherwise → wait interval, repeat
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

**After setup, always print the PR link so the user can click it:**
```
Babysitting PR: <PR_URL>
```

### 0b. Fast-Exit Check

Before entering the loop, check if the PR is already ready:

```bash
CHECKS=$(gh pr checks "$PR_NUMBER" --json name,state,conclusion 2>/dev/null || echo "[]")
MERGEABLE=$(echo "$PR_JSON" | jq -r '.mergeable')
MERGE_STATE=$(echo "$PR_JSON" | jq -r '.mergeStateStatus')
```

If ALL of the following are true:
- `MERGEABLE` is `"MERGEABLE"`
- `MERGE_STATE` is `"CLEAN"`
- **At least one check exists** (CHECKS is not empty) — OR the PR was created more than 5 minutes ago (checks genuinely absent, not just slow to register)
- Every check is in a terminal state (SUCCESS, NEUTRAL, or FAILURE) — no PENDING/QUEUED/IN_PROGRESS
- All required checks pass
- No review comments exist on the PR

Then print and exit immediately:
```
[ALREADY READY TO MERGE] <PR_URL>
```

If CHECKS is empty and the PR was created less than 5 minutes ago, do NOT fast-exit — wait for checks to be reported. Empty checks shortly after creation means GitHub hasn't registered them yet, not that CI is absent.

Otherwise, proceed to the loop.

### 0c. Initialize State

```
IDLE_ROUNDS_REMAINING = max-rounds (default 5)
MAX_TOTAL_ITERATIONS = max-rounds * 3    # hard cap to prevent infinite loops
TOTAL_ITERATIONS = 0
INTERVAL = interval (default 3m)
LAST_CHECKED = PR_CREATED_AT             # first pass processes all existing comments
TOTAL_WAIT_MINUTES = 0
CONSECUTIVE_READY_COUNT = 0              # must reach 2 before declaring ready
PUSHED_AT = None                         # set to current time after each push
EXTERNAL_CHECK_PATIENCE = 10             # separate counter for external check waits
DECISIONS = load_decisions(PR_NUMBER)    # comment_id → {decision, drafted_reply?, custom?} — persisted across iterations and skill runs
EXPLAINED_DIFF_SHA = load .claude/pr-babysit/<PR_NUMBER>/explained-diff.sha  # empty if missing
```

`DECISIONS` persists at `.claude/pr-babysit/<PR_NUMBER>/decisions.json`. Load on startup (create empty if missing), write after every human gate decision. This survives Ctrl-C, re-invocations, and worksheet round-trips so the user is never asked twice about the same comment.

`EXPLAINED_DIFF_SHA` is the sha256 of `git diff origin/<BASE_BRANCH>...HEAD` at the last `/pr-explain` refresh — the diff the explainer page currently matches. Empty means this run hasn't verified page currency yet. Written after every refresh; persisting it avoids republishing an unchanged page across re-invocations.

Three counters prevent infinite loops:
- `IDLE_ROUNDS_REMAINING` resets when progress is made (commit & push). Exhaustion means the PR stalled.
- `MAX_TOTAL_ITERATIONS` never resets. Exhaustion means the skill has been running too long regardless of progress.
- `EXTERNAL_CHECK_PATIENCE` counts down only when external checks are the sole blocker. Does NOT consume `IDLE_ROUNDS_REMAINING` — the PR isn't stalled, it's waiting for an external system.

## Phase 1: The Loop

Each iteration runs these phases in order. Evaluate exit conditions at the end.

**At the start of each iteration, print a status line:**
```
Round <TOTAL_ITERATIONS + 1> — <PR_URL>
```

### 1a. Check PR State

Before doing any work, verify the PR is still open:

```bash
PR_STATE=$(gh pr view "$PR_NUMBER" --json state -q '.state')
```

If `PR_STATE` is `MERGED` or `CLOSED`, print the PR URL and exit — no further action needed.

### 1b. Run Local Gates (first iteration only)

On the **first iteration only** (`TOTAL_ITERATIONS == 0`), run all gates from `.claude/gates.json` locally before checking remote CI. This catches failures immediately instead of waiting for remote CI to report them.

```bash
if [ -f .claude/gates.json ] && [ "$TOTAL_ITERATIONS" -eq 0 ]; then
  SETUP=$(jq -r '.setup // empty' .claude/gates.json)
  [ -n "$SETUP" ] && eval "$SETUP"
  for gate in $(jq -c '.gates[]' .claude/gates.json); do
    NAME=$(echo "$gate" | jq -r '.name')
    RUN=$(echo "$gate" | jq -r '.run')
    FIX=$(echo "$gate" | jq -r '.fix // empty')
    [ -n "$FIX" ] && eval "$FIX"
    if ! eval "$RUN"; then
      # Gate failed — fix the errors before proceeding
    fi
  done
fi
```

If any gate fails, fix the errors, commit, and push before continuing to 1c. This avoids a wasted wait cycle.

Skip on subsequent iterations — the existing gate run in step 1f (after comment fixes) handles those.

### 1c. Fetch New Data (Parallel)

Kick off all data fetches in parallel at the start of each iteration:

```bash
# All four in parallel:

# 1. Review comments (inline code comments on specific lines)
COMMENTS=$(gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments" \
  --paginate \
  -q '[.[] | select(.created_at > "'"$LAST_CHECKED"'") | {id, path, line, body, user: .user.login}]')

# 2. Review bodies (top-level review comments submitted with a review)
REVIEWS=$(gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/reviews" \
  --paginate \
  -q '[.[] | select(.submitted_at > "'"$LAST_CHECKED"'" and .body != "") | {id, body, user: .user.login, state}]')

# 3. Issue-level comments (top-level PR comments from bots and reviewers)
# IMPORTANT: GitHub bot comments (e.g., GitHub Actions, Cursor Bugbot) are posted
# to the issues endpoint, NOT the pulls/comments endpoint. Missing this means
# missing bot feedback entirely.
ISSUE_COMMENTS=$(gh api "repos/$OWNER/$REPO/issues/$PR_NUMBER/comments" \
  --paginate \
  -q '[.[] | select(.created_at > "'"$LAST_CHECKED"'") | {id, body, user: .user.login}]')

# 4. CI status + mergeable status
CHECKS=$(gh pr checks "$PR_NUMBER" --json name,state,conclusion,detailsUrl)
MERGEABLE=$(gh pr view "$PR_NUMBER" --json mergeable,mergeStateStatus)
```

**IMPORTANT:** You MUST fetch from all three comment endpoints. `pulls/N/comments` has inline review comments, `pulls/N/reviews` has review bodies, and `issues/N/comments` has top-level PR comments including bot feedback. Missing any endpoint means missing feedback.

Update `LAST_CHECKED` to current UTC timestamp after fetching.

### 1d. Categorize Comments

For each new comment (from inline comments, review bodies, AND issue-level comments), tag both the **author type** and the **category**.

**Author type:**
- **Bot** — `user.type == "Bot"` OR login ends in `[bot]` OR login is in the known-bot allowlist: `github-actions`, `cursor-bugbot`, `codecov`, `coderabbitai`, `renovate-bot`, `sonarcloud`. Belt-and-suspenders: check all three, not just one.
- **Human** — everything else.

**Category:**
1. **Actionable code change** — requests a specific code modification (e.g., "rename this variable", "add error handling here", "this should use X instead of Y")
2. **Question** — asks something that needs a reply (e.g., "why did you choose this approach?", "is this tested?")
3. **Informational / FYI** — no action needed (e.g., coverage reports, bot status messages, "LGTM", acknowledgements)
4. **Stale bot comment** — a bot reviewed an old commit and the referenced lines have changed since

Skip informational comments entirely. **Bot comments flow automatically through 1f/1g. Human comments MUST go through the 1e gate first — never auto-fix or auto-reply to a human.**

**Auto-dismiss stale bot comments:** For each bot comment, check if the referenced lines changed since the comment was posted:

```bash
# Get the commit SHA the comment refers to
COMMENT_COMMIT=$(echo "$COMMENT" | jq -r '.commit_id // empty')
# Check if the file at that line changed since that commit
git diff "$COMMENT_COMMIT"..HEAD -- "$FILE_PATH" | grep -q "^@@.*$LINE_NUMBER"
```

If the lines changed, auto-reply: "This was addressed in a subsequent commit." and skip the comment. Only process bot comments on unchanged code as actionable.

### 1e. Human Comment Gate

Human comments (actionable + question) require an explicit user decision before any code change or reply is posted. Bot comments do not enter this gate.

**1. Filter already-decided comments.** For each new human comment, look up `DECISIONS[comment_id]`:
- Decision `apply`, `push-back`, `dismiss` — skip (terminal, already handled or explicitly waived).
- Decision `defer` or no entry — include in the gate batch.
- If the comment body changed since the decision was recorded — include, re-present.

**2. Build a trade-off assessment per batched comment.** For each, READ the referenced file AND run `git blame` on the referenced line BEFORE drafting the assessment. Skipping this step makes the gate empty ceremony. Each assessment contains:

- **What's asked** — one-sentence paraphrase of the reviewer's request
- **Current code** — the referenced lines as they are now (actual snippet, not a description)
- **Proposed change** — what applying the comment would do, concretely
- **Pros / Cons** — factual tradeoffs
- **Blast radius** — files and call-sites affected
- **Effort** — rough time estimate
- **Drafted push-back** — a respectful reply the user can post if they disagree, grounded in the actual code

**3. Present assessments and collect decisions.**

**Fast path (≤ 5 human comments):** emit a single `AskUserQuestion` tool call with one question per comment (questions in parallel). Each question's `header` is `<author>@<path>:<line>`, `question` text is a terse 1-2 line summary of the ask, and the full assessment goes in the option descriptions where relevant. Offer these four options per comment:
- `Apply` — accept the feedback. For **actionable** comments: 1f applies the proposed change and posts `Fixed — <summary>`. For **questions**: 1g posts the drafted answer.
- `Push back` — reject the feedback. For **actionable**: no code change; 1g posts the drafted push-back reply. For **questions**: 1g posts a counter-argument drafted during the gate.
- `Defer` — no action this iteration. The comment will be re-presented next round (blocks readiness).
- `Dismiss` — no action, no reply. Treated as resolved locally (does NOT block readiness). Use when the user deems the comment not applicable.

**Slow path (> 5 human comments):** write all assessments to `.claude/pr-babysit/<PR_NUMBER>/decisions.md` with a `Decision:` field per comment (default `defer`). Print:

```
<N> human comments need decisions — edit .claude/pr-babysit/<PR_NUMBER>/decisions.md and re-invoke /pr-babysit to continue.
```

Then exit the skill (do NOT sleep and loop — the user may take hours to review). On the next invocation, Phase 0 detects the worksheet, parses `Decision:` lines into `DECISIONS`, archives the file to `decisions.md.done`, and resumes normal flow.

Worksheet format per comment:

```markdown
## <N>. @<author> — <path>:<line>
> <comment body>

**Current code:**
```<lang>
<snippet>
```

**Proposed change:** <...>
**Pros / Cons:** <...>
**Blast radius:** <...>
**Effort:** <...>
**Drafted push-back:** <...>

**Decision:** defer    <!-- one of: apply | push-back | defer | dismiss -->
```

**4. Persist `DECISIONS` to disk.** After every decision (AskUserQuestion response or worksheet parse), write `DECISIONS` to `.claude/pr-babysit/<PR_NUMBER>/decisions.json`. Schema: `{<comment_id>: {decision, drafted_reply?, custom?, comment_body_sha256, decided_at}}`. The `comment_body_sha256` lets step 1 above detect when the reviewer edited the comment.

**5. Gate-level readiness rule.** If any human comment lacks a terminal decision (`apply` / `push-back` / `dismiss`) after the gate runs, the PR is NOT ready this iteration — even if all other conditions are green.

### 1f. Fix All Actionable Comments

Process actionable comments, then run gates once.

**1. Bot actionable comments** (auto-flow, no gate):
- Read the referenced file at the referenced line
- Understand the reviewer's request in context
- Apply the fix
- Reply on the thread:
  ```bash
  gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments/$COMMENT_ID/replies" \
    -f body="Fixed — <brief description of what was changed>."
  ```

**2. Human actionable comments** — consult `DECISIONS[comment_id].decision`:
- `apply` — apply the change described in the assessment's "Proposed change", then post `Fixed — <summary>` reply (same API call as above).
- `push-back` — do NOT change code. The drafted push-back reply is posted in 1g, not here.
- `defer` — skip entirely this iteration. Do not change code, do not reply. Comment will be re-presented next round.
- `dismiss` — skip entirely. Do not change code, do not reply. Decision persists so this won't re-appear.

**3. After all fixes are applied**, run quick gates once:
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

### 1g. Reply to Questions

Fire replies in parallel.

**Bot questions** (rare): auto-reply with a concise, code-grounded answer.

**Human questions AND human push-backs from 1f:** post ONLY the reply approved in the gate. Look up `DECISIONS[comment_id].decision`:
- `apply` / `push-back` — post the drafted reply stored in `DECISIONS[comment_id].drafted_reply`. For `apply` the drafted reply is `Fixed — <summary>` (posted in 1f if the comment was actionable; posted here if it was a question). For `push-back` it's the rebuttal drafted during the gate.
- `defer` / `dismiss` — no reply this iteration.

Never write a human reply that wasn't approved in 1e.

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

### 1h. Fix CI Failures

From the checks data fetched in 1c, categorize each check:
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

### 1i. Resolve Merge Conflicts

From the mergeable data fetched in 1c, check if `mergeable` is `"CONFLICTING"` or `mergeStateStatus` is `"DIRTY"`.

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

### 1j. Evaluate and Act

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
6. **Set `PUSHED_AT` to current time** — starts the post-push cooldown
7. **Refresh the PR explainer** when the diff materially changed: `DIFF_SHA=$(git diff "origin/$BASE_BRANCH"...HEAD | sha256sum | cut -d' ' -f1)`; if it differs from `EXPLAINED_DIFF_SHA`, invoke the `pr-explain` skill (Skill tool, args: `$PR_NUMBER`), then write the new sha to the state file. The refresh republishes to the teaser's existing artifact URL — same link, updated page. A rebase-only push whose diff content is unchanged hashes the same and skips the refresh.

**Post-push cooldown:** If `PUSHED_AT` is set and less than 60 seconds have elapsed since the push, do NOT evaluate readiness. Checks may not be reported yet. Reset `CONSECUTIVE_READY_COUNT` to 0 and wait for the next iteration. Also: if checks are empty and less than 2 minutes have elapsed since `PUSHED_AT`, treat this as "checks pending" not "no checks configured."

**Unreplied comments check:** Before evaluating readiness, fetch ALL review comments on the PR (not just new ones) and check if any actionable comments have no reply. An unreplied actionable comment is a blocking issue — it means feedback was not addressed.

```bash
# Fetch all review comments and check for unreplied ones
ALL_COMMENTS=$(gh api "repos/$OWNER/$REPO/pulls/$PR_NUMBER/comments" --paginate)
# A comment is "unreplied" if it has no replies (check via in_reply_to_id)
# Exclude: bot comments, informational comments, comments authored by the current user
```

Treat unreplied comments by author type:
- **Unreplied bot comments** — route to step 1f and fix them, reply confirming the fix, then re-evaluate.
- **Unreplied human comments with a terminal decision** (`apply` / `push-back`) — route to 1f/1g to execute the approved action. Don't re-gate.
- **Unreplied human comments with `dismiss`** — do not block readiness. User waived the reply.
- **Unreplied human comments with `defer` or no cached decision** — route back to the 1e gate this iteration. These DO block readiness.

**HARD RULE: NEVER declare `[READY TO MERGE]` when ANY check shows state "pending", "queued", or "in_progress". No exceptions. No "non-required" distinction. No "external check" bypass. If a check is registered on the PR, it MUST reach a terminal state before readiness can be evaluated. Terminal states: SUCCESS, FAILURE, NEUTRAL, SKIPPED (with duration > 0). Non-terminal: PENDING, QUEUED, IN_PROGRESS, SKIPPED (with duration 0 — still initializing).**

**If no changes were needed** AND **no unreplied comments exist** AND **at least one check exists** (not empty) AND **every** check has reached a terminal state AND all required checks pass AND no conflicts:
→ Increment `CONSECUTIVE_READY_COUNT`
→ If `CONSECUTIVE_READY_COUNT >= 2`: recompute `DIFF_SHA`; if it differs from `EXPLAINED_DIFF_SHA`, invoke `pr-explain` once more and store the sha — the page must match the final diff. Then print and exit:
```
[READY TO MERGE] <PR_URL>
```
→ If `CONSECUTIVE_READY_COUNT < 2`: **immediately** re-fetch all data (skip the wait) and re-check. This double-check avoids race conditions where checks or comments arrive between fetches, without adding unnecessary delay.

**If no changes were needed** but any check is still running (PENDING, QUEUED, IN_PROGRESS) or `mergeStateStatus` is UNSTABLE:
→ This is **not** ready. Reset `CONSECUTIVE_READY_COUNT` to 0.
→ Check if the ONLY blocker is pending external checks (all code CI checks pass, only external tools like Cursor Bugbot are pending):
  - If yes: log "Waiting for external check: <name>". Decrement `EXTERNAL_CHECK_PATIENCE` (NOT `IDLE_ROUNDS_REMAINING`). The PR isn't stalled — it's waiting for an external system.
  - If no (code CI checks are also failing/pending): decrement `IDLE_ROUNDS_REMAINING` as normal.
→ Wait and re-check next iteration.

**If no changes were needed** and all checks are terminal but some required checks failed with unfixable issues:
→ Reset `CONSECUTIVE_READY_COUNT` to 0, decrement `IDLE_ROUNDS_REMAINING`

### 1k. Check Exit Conditions

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

**External check patience exhausted** (`EXTERNAL_CHECK_PATIENCE <= 0`):
→ Print and exit:
```
[MAX ROUNDS EXHAUSTED] external checks never completed after <TOTAL_WAIT_MINUTES> minutes. <PR_URL>
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
| Waiting twice in one iteration | Wait happens in exactly one place: step 1k |
| Replying to top-level reviews via comment reply API | Top-level review bodies use `gh pr comment`, inline comments use the replies API |
| Declaring ready when checks are empty | Empty checks after push = pending, not absent. Wait 60s minimum after push, require at least one check before declaring ready. |
| Declaring ready with pending external checks | ALL checks must be terminal. No "non-required" exceptions. No "external check" bypass. |
| Rationalizing around UNSTABLE merge state | UNSTABLE = not ready, period. Wait and re-check. |
| Counting external check waits against idle rounds | Use `EXTERNAL_CHECK_PATIENCE` for external-only waits, not `IDLE_ROUNDS_REMAINING`. |
| Declaring ready with unreplied comments | ALL actionable comments must be addressed and replied to before declaring ready. |
| Only fetching pulls/N/comments | MUST also fetch issues/N/comments — bot comments (GitHub Actions, Cursor Bugbot) are posted there, not on the review endpoint. |
| Auto-fixing or auto-replying to a human comment | Human comments (actionable or question) MUST go through the 1e gate. Never post a reply or change code for a human without a cached `apply` / `push-back` decision. |
| Asking the user twice about the same comment | Check `DECISIONS[comment_id]` in 1e; skip any comment with a terminal decision. Re-present only when body changed or decision was `defer`. |
| Skipping the read-and-blame step before drafting the assessment | Empty ceremony. Always read the referenced file and run `git blame` on the line before writing the assessment — otherwise the gate adds friction without value. |
| Detecting bots by login suffix only | Check all three: `user.type == "Bot"`, login ends in `[bot]`, login in the known-bot allowlist. Bots like `cursor-bugbot` don't have the `[bot]` suffix. |
| Sleeping/looping while waiting for the worksheet | When >5 human comments trigger the slow path, exit the skill — do NOT sleep indefinitely. User re-invokes after editing the file. |
| Declaring ready while a human comment is `defer` | `defer` is explicitly "decide later" — it blocks readiness. Only `apply` / `push-back` / `dismiss` (and bot completion) clear the readiness check. |
| Minting a new artifact URL on refresh | /pr-explain reuses the teaser's URL (its Phase 5) — a refresh lands on the same link, or the link reviewers already have goes stale |
| Skipping the explainer refresh when headless | /pr-explain writes the story as markdown between its PR-body markers on its own — invoke it regardless |
| Refreshing the explainer every round | Hash the diff; only a changed hash (a material change) or the final READY check warrants a refresh |
