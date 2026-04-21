#!/usr/bin/env bash
# One-shot uninstall — restores backups recorded during install.
exec "$(dirname "$0")/at" uninstall "$@"
