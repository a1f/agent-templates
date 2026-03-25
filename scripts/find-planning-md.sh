#!/usr/bin/env bash
set -euo pipefail

# Find planning .md files at the repository root, excluding standard repo docs.
# Usage: find-planning-md.sh
# Outputs newline-separated absolute paths. Exits 0 even if none found.

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null || pwd)

# Standard repo docs to exclude (not planning artifacts)
EXCLUDE_PATTERN='(README|CHANGELOG|LICENSE|CONTRIBUTING|CODE_OF_CONDUCT|CLAUDE)\.md$'

found=0
for f in "$REPO_ROOT"/*.md; do
  [ -f "$f" ] || continue
  fname=$(basename "$f")
  if ! echo "$fname" | grep -qE "$EXCLUDE_PATTERN"; then
    echo "$f"
    found=1
  fi
done

exit 0
