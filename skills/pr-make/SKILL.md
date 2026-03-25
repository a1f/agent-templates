---
name: pr-make
description: Use when the user invokes /pr-make to create or update a pull request. Alias for /make-pr.
---

# PR Make (Alias)

This is an alias for the `/make-pr` skill. Use the Skill tool to invoke `make-pr` with all arguments the user provided.

See `/make-pr` for available arguments: `--issue`, `--reviewers`, `--title`, `--base`, `--draft`.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Reimplementing PR creation logic | ALWAYS dispatch to `/make-pr` — never duplicate its behavior |
| Dropping user arguments | Forward all arguments exactly as provided |
