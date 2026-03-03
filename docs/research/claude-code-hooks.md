# Research: Claude Code Hooks System

## Current State of the Art

Claude Code hooks are shell scripts or LLM prompts triggered by lifecycle events. They enable automation (auto-approve safe operations), notifications (Slack), and guardrails (security checks).

## Hook Configuration

### Plugin hooks.json Format

```json
{
  "description": "Brief explanation",
  "hooks": {
    "EventName": [
      {
        "matcher": "pattern",
        "hooks": [
          {
            "type": "command",
            "command": "bash script.sh",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

### User settings.json Format

```json
{
  "hooks": {
    "EventName": [
      {
        "matcher": "pattern",
        "hooks": [
          {
            "type": "command",
            "command": "bash ~/.claude/hooks/script.sh",
            "timeout": 60
          }
        ]
      }
    ]
  }
}
```

## Hook Types

| Type | Use Case | Supported Events |
|------|----------|-----------------|
| `command` | Deterministic validation, file ops | All events |
| `prompt` | LLM-based context-aware decisions | Stop, SubagentStop, UserPromptSubmit, PreToolUse |

## Event Types

| Event | Trigger | Key Output |
|-------|---------|-----------|
| `PreToolUse` | Before any tool runs | `permissionDecision: allow|deny|ask` |
| `PostToolUse` | After tool completes | systemMessage feedback |
| `Stop` | Agent wants to stop | `decision: approve|block` |
| `SubagentStop` | Subagent stops | Same as Stop |
| `UserPromptSubmit` | User sends prompt | systemMessage context |
| `SessionStart` | Session begins | Can set env vars via `$CLAUDE_ENV_FILE` |
| `SessionEnd` | Session ends | Cleanup/logging |
| `PreCompact` | Before context compaction | Preserve critical info |
| `Notification` | User notification | React/log |

## Hook Input (stdin JSON)

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.jsonl",
  "cwd": "/current/working/directory",
  "hook_event_name": "PreToolUse",
  "tool_name": "Write",
  "tool_input": { "file_path": "/path", "content": "..." }
}
```

Event-specific fields: `tool_name`/`tool_input` (PreToolUse), `tool_result` (PostToolUse), `user_prompt` (UserPromptSubmit), `reason` (Stop).

## Hook Output

### Standard output:
```json
{
  "continue": true,
  "suppressOutput": false,
  "systemMessage": "Message for Claude"
}
```

### PreToolUse output:
```json
{
  "hookSpecificOutput": {
    "permissionDecision": "allow",
    "updatedInput": {}
  }
}
```

### Stop output:
```json
{
  "decision": "approve|block",
  "reason": "Explanation"
}
```

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success (stdout shown in transcript) |
| `2` | Blocking error (stderr fed to Claude) |
| Other | Non-blocking error |

## Matcher Patterns

```
"Write"              → exact tool name
"Read|Write|Edit"    → multiple tools (regex OR)
"*"                  → all tools
"mcp__.*"            → all MCP tools
""                   → empty string (matches all for non-tool events)
```

## Environment Variables

| Variable | Available In | Purpose |
|----------|-------------|---------|
| `$CLAUDE_PROJECT_DIR` | All hooks | Project root path |
| `$CLAUDE_PLUGIN_ROOT` | Plugin hooks | Plugin directory (for portable paths) |
| `$CLAUDE_ENV_FILE` | SessionStart only | Persist env vars |

## Script Best Practices

```bash
#!/bin/bash
set -euo pipefail

# Read input from stdin
input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name')

# Validate
if [[ "$tool_name" == "dangerous_thing" ]]; then
    echo '{"hookSpecificOutput":{"permissionDecision":"deny"}}' >&2
    exit 2
fi

# Allow (silent success)
exit 0
```

## Alternatives Evaluated

- **Prompt hooks**: More flexible for nuanced decisions but slower and cost tokens
- **Command hooks**: Fast, deterministic, no token cost — better for permission decisions
- **Hookify plugin**: YAML-based hook definitions, more user-friendly but adds dependency

**Recommendation:** Use command hooks for permission decisions and notifications. Reserve prompt hooks for complex context-dependent decisions.

## Key Findings for Implementation

1. Use `command` type for auto-approve and Slack notification hooks
2. Exit code `0` = allow, exit code `2` = block (stderr goes to Claude)
3. Read JSON from stdin with `jq` for parsing
4. Matcher uses regex — use `""` for non-tool events, tool names for PreToolUse
5. All matching hooks run in parallel — hooks must be independent
6. Hooks NOT hot-swappable — changes require session restart
7. Use `$CLAUDE_PROJECT_DIR` for project-aware hooks

## Sources

- Plugin hook examples: `~/.claude/plugins/cache/claude-plugins-official/superpowers/4.3.1/hooks/`
- Security guidance hook: `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/security-guidance/`
- Ralph loop stop hook: `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/ralph-loop/`
- Hook development skill: `~/.claude/plugins/marketplaces/claude-plugins-official/plugins/plugin-dev/skills/hook-development/`
