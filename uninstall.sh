#!/usr/bin/env bash
# One-shot uninstall — removes all components installed via ./at.
exec "$(dirname "$0")/at" uninstall --all "$@"
