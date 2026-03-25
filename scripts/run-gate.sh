#!/usr/bin/env bash
set -euo pipefail

# Run a single gate from .claude/gates.json and report pass/fail.
# Usage: run-gate.sh --gate=<name> [--fix-first]
# Exit 0 = pass, Exit 1 = fail (stderr has error output)

GATE_NAME=""
FIX_FIRST="false"

for arg in "$@"; do
  case "$arg" in
    --gate=*) GATE_NAME="${arg#--gate=}" ;;
    --fix-first) FIX_FIRST="true" ;;
    --help|-h)
      echo "Usage: run-gate.sh --gate=<name> [--fix-first]"
      echo "  Reads .claude/gates.json and runs the named gate."
      echo "  --fix-first: run the gate's fix command before checking."
      echo "  Exit 0 = pass, Exit 1 = fail."
      exit 0
      ;;
    *) echo "Unknown argument: $arg" >&2; exit 2 ;;
  esac
done

if [ -z "$GATE_NAME" ]; then
  echo "Error: --gate=<name> is required" >&2
  exit 2
fi

GATES_FILE=".claude/gates.json"
if [ ! -f "$GATES_FILE" ]; then
  echo "Error: $GATES_FILE not found" >&2
  exit 2
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is required" >&2
  exit 2
fi

# Extract gate config
GATE_JSON=$(jq -r --arg name "$GATE_NAME" '.gates[] | select(.name == $name)' "$GATES_FILE")

if [ -z "$GATE_JSON" ] || [ "$GATE_JSON" = "null" ]; then
  echo "Error: gate '$GATE_NAME' not found in $GATES_FILE" >&2
  exit 2
fi

RUN_CMD=$(echo "$GATE_JSON" | jq -r '.run')
FIX_CMD=$(echo "$GATE_JSON" | jq -r '.fix // empty')

# Run setup if present and not already done this session
SETUP_CMD=$(jq -r '.setup // empty' "$GATES_FILE")
SETUP_MARKER="${TMPDIR:-/tmp}/.claude-gate-setup-$$"

if [ -n "$SETUP_CMD" ] && [ ! -f "$SETUP_MARKER" ]; then
  if ! eval "$SETUP_CMD" >&2; then
    echo "Error: setup command failed: $SETUP_CMD" >&2
    exit 1
  fi
  touch "$SETUP_MARKER"
fi

# Run fix command first if requested
if [ "$FIX_FIRST" = "true" ] && [ -n "$FIX_CMD" ]; then
  eval "$FIX_CMD" >&2 2>&1 || true
fi

# Run the gate check
if eval "$RUN_CMD" 2>&1; then
  exit 0
else
  exit 1
fi
