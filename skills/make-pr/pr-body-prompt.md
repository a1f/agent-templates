# PR Body Generator Prompt

Generate a pull request title and body from the provided context.

## Input

You receive:
- **Issue:** GitHub issue title and body (if linked), or `null`
- **Commits:** Output of `git log ${BASE}..HEAD --oneline`
- **Diff stats:** Output of `git diff ${BASE}...HEAD --stat`
- **Gates passed:** List of gates that ran and passed

## Title Rules

- Under 70 characters
- Start with a conventional commit prefix: `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`
- Describe the user-facing change, not implementation details
- If linked to an issue, the title should reflect the issue's goal

## Body Format

```markdown
## Summary

<2-4 bullet points describing what changed and why>

## Changes

<Grouped list of notable changes by area — not a commit-by-commit log>

## Testing

<What gates passed, what was tested>

## Issue

<Closes #N — or "No linked issue" if none>

---
Generated with [Claude Code](https://claude.com/claude-code)
```

## Rules

- Write for the reviewer: what do they need to know to review this PR?
- Summarize, don't repeat the full diff
- If the PR fixes gate errors (lint, typecheck), mention it briefly but don't list every fix
- If there are known issues from review, add a `## Known Issues` section
- Keep it concise — a PR body longer than 30 lines is too long
