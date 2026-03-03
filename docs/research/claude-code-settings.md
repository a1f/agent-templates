# Research: Claude Code Settings & CLAUDE.md Patterns

## Current State of the Art

Claude Code uses two main configuration mechanisms:
1. **CLAUDE.md** — project-level instructions loaded into every conversation
2. **settings.json** — user/project-level configuration for hooks, permissions, and behavior

## CLAUDE.md

### Location & Loading

| File | Scope | Loaded When |
|------|-------|-------------|
| `<project>/CLAUDE.md` | Project root | Always (for this project) |
| `<project>/.claude/CLAUDE.md` | Project (hidden) | Always (for this project) |
| `~/.claude/CLAUDE.md` | User global | Always (all projects) |

All CLAUDE.md files are loaded and concatenated. Project-level takes precedence.

### Content Patterns

From superpowers and real projects, effective CLAUDE.md files include:
- Project overview (1-2 sentences)
- Tech stack and key dependencies
- Build/test/lint commands
- File structure overview
- Coding conventions (or reference to rules/)
- Workflow instructions (reference to skills)
- Context management patterns (progress.md + /clear + continue)

### Best Practices

- Keep concise — CLAUDE.md is loaded every conversation, wasting tokens if verbose
- Reference rules/ for language-specific conventions (conditional loading)
- Reference skills for workflows (loaded on demand)
- Include commands Claude needs: build, test, lint, format
- Document non-obvious project patterns

## settings.json

### Location

| File | Scope |
|------|-------|
| `~/.claude/settings.json` | User global |
| `<project>/.claude/settings.json` | Project-specific |

### Schema (relevant fields)

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "pattern",
        "hooks": [
          { "type": "command", "command": "...", "timeout": 60 }
        ]
      }
    ]
  },
  "permissions": {
    "allow": ["Read", "Glob", "Grep"],
    "deny": []
  }
}
```

## How Skills, Rules, Hooks, and CLAUDE.md Interact

```
Session Start
  ├── Load CLAUDE.md (always)
  ├── Load unconditional rules (always)
  ├── Load settings.json hooks
  │
  ├── User opens file.py
  │   └── Load conditional rules matching **/*.py
  │
  ├── User says "/implement"
  │   └── Load matching skill by description
  │
  └── Tool call → PreToolUse hooks fire
      └── Auto-approve hook checks tool name
```

## Key Findings for Implementation

1. CLAUDE.md template should be concise — reference rules/skills, don't duplicate them
2. settings.json hook config goes under `"hooks"` key at top level
3. Installer needs to merge hooks into existing settings.json (not overwrite)
4. Keep CLAUDE.md under ~200 lines to avoid context waste
5. Document the skill entry points (e.g., `/implement-orchestrator`)

## Sources

- [Claude Code Docs: Memory management](https://code.claude.com/docs/en/memory)
- Superpowers plugin settings patterns
- Real-world CLAUDE.md files from various projects
