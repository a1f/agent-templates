#!/usr/bin/env bash
# Backwards-compatible wrapper — delegates to ./at validate
exec "$(dirname "$0")/at" validate "$@"
