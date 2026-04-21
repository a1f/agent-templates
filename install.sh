#!/usr/bin/env bash
# One-shot install — installs all components non-interactively.
# Safe to re-run; overwritten files are backed up to .bak.<timestamp>.
# For the interactive component picker or advanced flags, run ./at install directly.
exec "$(dirname "$0")/at" install --all --non-interactive "$@"
