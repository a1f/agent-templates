---
name: plan-code
description: Use when the user invokes /plan-code to plan code changes with clean code principles. Alias for /clean-code-planner.
---

# Plan Code (Alias)

This is an alias for the `/clean-code-planner` skill. Use the Skill tool to invoke `clean-code-planner` with all arguments the user provided.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Reimplementing planning logic | ALWAYS dispatch to `/clean-code-planner` — never duplicate its behavior |
| Dropping user arguments | Forward all arguments exactly as provided |
