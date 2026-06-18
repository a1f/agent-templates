#!/usr/bin/env bash
# PostToolUse hook: format the .py file Claude just edited with ruff.
# Reads the hook JSON payload on stdin; formats only existing .py files and
# otherwise no-ops, so it is safe to run after any tool call.
set -euo pipefail
# Without jq there is nothing to parse, and a malformed payload yields no path:
# either way no-op rather than aborting under set -e (jq-missing is exit 127,
# malformed JSON is exit 5), so the hook stays safe after any tool call.
command -v jq >/dev/null 2>&1 || exit 0
file_path="$(jq -r '.tool_input.file_path // empty' 2>/dev/null || true)"
[[ "$file_path" == *.py && -f "$file_path" ]] || exit 0
command -v ruff >/dev/null 2>&1 || exit 0
# End-of-options guard: a stdin-derived path beginning with '-' must be treated as
# a filename, never parsed as a ruff flag.
ruff format -- "$file_path" >/dev/null 2>&1 || true
