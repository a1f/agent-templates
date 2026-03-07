# Research: Slack Incoming Webhooks API

## Format

Simple `"text"` payload is still fully supported. Block Kit is optional and additive.

### Recommended Payload
```json
{
  "text": "Claude Code [Stop]: project-name needs your attention",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Claude Code Stop*\n*Project:* `project-name`\n*Time:* 2026-03-02 14:30 UTC"
      }
    }
  ]
}
```

The `"text"` field serves as fallback for mobile/desktop notifications when `"blocks"` are present.

## Rate Limits

- 1 message/second/channel. Short bursts tolerated.
- HTTP 429 on limit exceeded with `Retry-After` header.
- Not a concern for our use case (Notification/Stop events are infrequent).

## Error Handling

| HTTP Code | Meaning |
|-----------|---------|
| 200 | Success |
| 400 | Invalid payload / missing text |
| 403 | Workspace restriction |
| 404 | Webhook deleted / channel not found |
| 410 | Channel archived |
| 429 | Rate limited |

## Security

- Store URL in `CLAUDE_SLACK_WEBHOOK_URL` env var only
- Never commit webhook URLs (Slack actively scans repos and revokes leaked URLs)
- Mask URL in error output (show only last 6 chars)
- No request signing mechanism — treat URL like a password

## Implementation Pattern
```bash
#!/usr/bin/env bash
set -euo pipefail
WEBHOOK_URL="${CLAUDE_SLACK_WEBHOOK_URL:-}"
[[ -z "$WEBHOOK_URL" ]] && exit 0  # Silently skip if not configured

HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST -H "Content-type: application/json" \
  --data "$PAYLOAD" --max-time 5 "$WEBHOOK_URL" 2>/dev/null) || true

[[ "$HTTP_STATUS" != "200" ]] && echo "notify-slack: HTTP $HTTP_STATUS" >&2
```

## Threading via Web API

Incoming webhooks cannot update messages or return the message `ts` (timestamp), so threading
requires the Slack Web API with a bot token.

### Key API Methods

| Method | Purpose |
|--------|---------|
| `chat.postMessage` | Post a new message; returns `ts` for threading |
| `chat.update` | Update an existing message by `ts` |

### Bot Token Setup

1. Create a Slack app at [api.slack.com/apps](https://api.slack.com/apps)
2. Under **OAuth & Permissions**, add scopes: `chat:write`
3. Install to workspace → copy **Bot User OAuth Token** (`xoxb-...`)
4. Invite the bot to the target channel (`/invite @BotName`)

### Threading Pattern

```
Session start → chat.postMessage → save ts to /tmp/claude-slack-<session_id>
Notification  → chat.postMessage with thread_ts = saved ts (threaded reply)
Stop          → chat.update parent ts with final status + threaded reply
```

State is ephemeral (stored in `/tmp`). If state is lost, next event simply posts a new parent.

### Required Scopes

| Scope | Reason |
|-------|--------|
| `chat:write` | Post and update messages |

No other scopes needed. The bot does not read messages or access user data.

## Alternative: Discord Webhooks

Discord offers a Slack-compatible endpoint by appending `/slack` to a Discord webhook URL. Same payload format works. Consider as future enhancement.

## Sources

- [Slack: Sending messages using incoming webhooks](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/)
- [Slack: Rate limits](https://docs.slack.dev/apis/web-api/rate-limits/)
- [Slack: Security best practices](https://docs.slack.dev/authentication/best-practices-for-security/)
- [Slack: chat.postMessage](https://api.slack.com/methods/chat.postMessage)
- [Slack: chat.update](https://api.slack.com/methods/chat.update)
- [Slack: Message threading](https://api.slack.com/docs/message-threading)
