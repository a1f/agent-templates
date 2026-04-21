#!/usr/bin/env bash
set -euo pipefail

# Claude Code PostToolUse hook: Inject GitHub issue awareness when entering plan mode.
# Matcher: EnterPlanMode
# Reads JSON from stdin and outputs a systemMessage instructing Claude to check
# for related GitHub issues before planning.
# Fails open (exit 0, no output) if jq is unavailable or any error occurs.

# Fail open if jq is not installed
if ! command -v jq &>/dev/null; then
  exit 0
fi

# Short-circuit when this environment cannot act on GitHub issues. Teammates
# on GitLab, internal Git servers, or hosts without gh installed should not
# see the GitHub-specific planning playbook on every EnterPlanMode event.
command -v gh >/dev/null 2>&1 || exit 0
gh auth status >/dev/null 2>&1 || exit 0
git rev-parse --show-toplevel >/dev/null 2>&1 || exit 0
git remote -v 2>/dev/null | grep -q 'github\.com' || exit 0

# Read hook input from stdin
input=$(cat)

# Verify this is an EnterPlanMode event
tool_name=$(echo "$input" | jq -r '.tool_name // ""')
if [[ "$tool_name" != "EnterPlanMode" ]]; then
  exit 0
fi

# Output systemMessage instructing Claude to check for related issues
cat <<'SYSMSG'
{"hookSpecificOutput":{"systemMessage":"GITHUB ISSUE INTEGRATION: Before starting this plan, check for related GitHub issues.\n\n1. Run: gh issue list --limit 20 --state open --json number,title,labels\n2. Analyze which issues relate to the task the user is about to plan.\n3. If related issues are found, use AskUserQuestion: \"I found these related GitHub issues:\\n- #N title\\n- #N title\\nShould I link any of these as tracking issues for this plan?\"\n4. If no related issues are found, ask: \"No related GitHub issues found. Would you like me to create a tracking issue for this plan?\"\n5. If the user wants to create an issue, draft a title and body from context, show it for confirmation, then run: gh issue create --title \"...\" --body \"...\"\n6. Record the linked or created issue number in the plan file header (e.g., \"GitHub Issue: #N\").\n7. If gh is not installed, not authenticated, or this is not a GitHub repo, skip silently and proceed with planning."}}
SYSMSG

exit 0
