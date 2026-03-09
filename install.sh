#!/usr/bin/env bash
# Backwards-compatible wrapper — delegates to ./at install
exec "$(dirname "$0")/at" install "$@"
