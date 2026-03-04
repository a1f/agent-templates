#!/usr/bin/env bash
set -euo pipefail

# Claude Code hook: Send Slack notifications on Notification and Stop events.
# Usage: notify-slack.sh <event_type>
#   event_type: "notification" or "stop"
#
# Configured via CLAUDE_SLACK_WEBHOOK_URL environment variable.
# Silently exits if the webhook URL is not set.
# Never blocks Claude — always exits 0.

EVENT_TYPE="${1:-unknown}"
WEBHOOK_URL="${CLAUDE_SLACK_WEBHOOK_URL:-}"

# Silently exit if webhook URL is not configured
[[ -z "$WEBHOOK_URL" ]] && exit 0

# Extract repo name and branch
PROJECT_NAME="${PWD##*/}"
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")

# Generate UTC timestamp
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M UTC")

# Build display label from event type
case "$EVENT_TYPE" in
  notification)
    EVENT_LABEL="Needs Input"
    DESCRIPTION="Claude Code is waiting for your input"
    ;;
  stop)
    EVENT_LABEL="Task Finished"
    DESCRIPTION="Claude Code has finished the task"
    ;;
  *)
    EVENT_LABEL="Event"
    DESCRIPTION="Claude Code event: $EVENT_TYPE"
    ;;
esac

# Build JSON payload with Block Kit support
# "text" serves as fallback for mobile/desktop notifications
PAYLOAD=$(cat <<EOF
{
  "text": "Claude Code [$EVENT_LABEL]: $PROJECT_NAME ($BRANCH) needs your attention",
  "blocks": [
    {
      "type": "section",
      "text": {
        "type": "mrkdwn",
        "text": "*Claude Code $EVENT_LABEL*\n*Repo:* \`$PROJECT_NAME\`  *Branch:* \`$BRANCH\`\n*Time:* $TIMESTAMP\n$DESCRIPTION"
      }
    }
  ]
}
EOF
)

# Send to Slack with 5-second timeout, capture HTTP status code
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" \
  -X POST \
  -H "Content-type: application/json" \
  --max-time 5 \
  --data "$PAYLOAD" \
  "$WEBHOOK_URL" 2>/dev/null) || true

# Log errors to stderr with masked webhook URL (last 6 chars only)
if [[ "$HTTP_STATUS" != "200" ]]; then
  MASKED_URL="...${WEBHOOK_URL: -6}"
  echo "notify-slack: HTTP $HTTP_STATUS (webhook: $MASKED_URL)" >&2
fi

# Never block Claude — always exit 0
exit 0
