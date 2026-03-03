#!/usr/bin/env bash
set -euo pipefail

# Claude Code PreToolUse hook: Auto-approve safe read-only tools.
# Reads JSON from stdin and outputs a permissionDecision for whitelisted tools.
# For all other tools, exits silently to let the normal permission flow continue.
# Fails open (exit 0, no output) if jq is unavailable.

# Fail open if jq is not installed
if ! command -v jq &>/dev/null; then
  exit 0
fi

# Read hook input from stdin
input=$(cat)

# Extract tool name from JSON input
tool_name=$(echo "$input" | jq -r '.tool_name // ""')

# Safe read-only tools that can be auto-approved
case "$tool_name" in
  Read|Glob|Grep|LS|WebSearch|WebFetch|NotebookRead)
    echo '{"hookSpecificOutput":{"permissionDecision":"allow"}}'
    ;;
esac

# For all other tools: exit 0 with no output (falls through to user prompt)
exit 0
