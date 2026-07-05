#!/usr/bin/env bash
# One-shot install of the whole catalog: bundles, packages, and units are all staged
# under ~/.claude/at and symlinked into ~/.claude. Safe to re-run — it reconciles, and a
# colliding real file at a link target is backed up to .bak and restored on uninstall.
# For the interactive menu, run ./at install.
exec "$(dirname "$0")/at" install --all --non-interactive "$@"
