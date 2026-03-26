---
name: review-and-fix
description: Use when the user wants to review code changes and fix any findings, or invokes /review-and-fix. Reviews the current diff, fixes CRITICAL and MAJOR issues, and commits fixes.
---

# Review and Fix

Review the current diff for issues, then fix them. Combines review and remediation in a single pass.

```
/review-and-fix [--base=branch] [--max-rounds=3]

  1. Review the diff for CRITICAL/MAJOR/MINOR issues
  2. Fix CRITICAL and MAJOR issues
  3. Re-review to verify fixes didn't introduce new issues
  4. Repeat until clean or max rounds reached
```

## Arguments

| Arg | Default | Example |
|-----|---------|---------|
| `--base=branch` | Default branch | `--base=main` |
| `--max-rounds=N` | `3` | `--max-rounds=5` |

## Phase 1: Review

### 1a. Determine the Diff

```bash
BASE_BRANCH="${ARG_BASE:-$(gh repo view --json defaultBranchRef -q '.defaultBranchRef.name' 2>/dev/null || echo 'main')}"
git diff "${BASE_BRANCH}...HEAD"
```

If no commits ahead of base, review staged + unstaged changes instead:
```bash
git diff HEAD
```

If no changes at all, tell the user there's nothing to review.

### 1b. Review the Diff

Review the diff yourself. Categorize each finding by severity:

| Severity | Criteria | Action |
|----------|----------|--------|
| **CRITICAL** | Security vulnerabilities, crashes, data corruption, data loss | Fix immediately |
| **MAJOR** | Logic errors, spec violations, race conditions, broken error handling | Fix immediately |
| **MINOR** | Suboptimal patterns, missing edge cases, weak naming | Fix if quick, otherwise note |
| **LOW** | Style preferences, minor readability | Skip — gates handle these |

**Do NOT flag:** formatting, import order, lint issues — gates handle those. Focus on correctness and logic.

### 1c. Report Findings

Print all findings before fixing:

```
## Review Findings

**CRITICAL (0):**
(none)

**MAJOR (2):**
1. `src/auth.py:42` — SQL injection via unsanitized user input
2. `src/handler.py:88` — Race condition: shared state modified without lock

**MINOR (1):**
1. `src/utils.py:15` — Missing null check on optional parameter

**LOW (0):**
(none)
```

## Phase 2: Fix

### 2a. Fix CRITICAL and MAJOR Issues

For each CRITICAL and MAJOR finding:
1. Read the file at the referenced location
2. Understand the surrounding context
3. Apply the fix
4. Verify the fix doesn't break adjacent logic

Fix MINOR issues only if the fix is quick (< 5 lines) and low-risk.

### 2b. Run Quick Gates

If `.claude/gates.json` exists, run format and lint gates after fixes:

```bash
if [ -f .claude/gates.json ]; then
  SETUP=$(jq -r '.setup // empty' .claude/gates.json)
  [ -n "$SETUP" ] && eval "$SETUP"
  for fix_cmd in $(jq -r '.gates[] | select(.fix != null) | .fix' .claude/gates.json); do
    eval "$fix_cmd"
  done
fi
```

### 2c. Commit Fixes

If any changes were made:
```bash
git add -A
git commit -m "fix: address review findings — <summary of what was fixed>"
```

## Phase 3: Re-review (Loop)

After fixing, re-review **only the new diff** (changes introduced by the fix commit, not the full diff again):

```bash
git diff HEAD~1...HEAD
```

If new CRITICAL or MAJOR issues were introduced by the fixes:
→ Fix them, commit, re-review again
→ Max `--max-rounds` iterations (default 3)

If no new issues:
→ Print summary and exit

## Final Output

```
## Review Complete

Rounds: <N>
Fixed: <count> CRITICAL, <count> MAJOR, <count> MINOR
Remaining: <count> issues noted but not fixed (MINOR/LOW)

Files modified:
- <list of files changed by fix commits>
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Fixing LOW/style issues | Gates handle style — review fixes logic only |
| Reviewing the full diff on re-review | Only review the fix commit's diff, not the entire branch diff |
| Introducing new bugs while fixing | Verify each fix in context; re-review catches regressions |
| Fixing without understanding context | Read surrounding code before applying fixes |
| Committing review fixes with unrelated changes | Only stage files modified by review fixes |
