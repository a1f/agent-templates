#!/usr/bin/env bash
set -euo pipefail

# Claude Code hook: Send Slack notifications on Notification and Stop events.
# Usage: notify-slack.sh <event_type>
#   event_type: "notification" or "stop"
#   Reads JSON from stdin for event context (message, session_id, etc.)
#
# Configuration (environment variables):
#   CLAUDE_SLACK_WEBHOOK_URL  — Incoming webhook URL (simple mode, no threading)
#   CLAUDE_SLACK_BOT_TOKEN    — Bot token for Slack Web API (enables threading)
#   CLAUDE_SLACK_CHANNEL      — Channel ID for Web API mode (required with bot token)
#
# Threading mode (bot token):
#   - First message per session becomes the parent
#   - Subsequent events post as threaded replies
#   - Stop event updates the parent message with final status
#   - Session state stored in /tmp/claude-slack-<session_id>
#
# Webhook-only mode (no bot token):
#   - Posts individual messages with context from stdin
#   - No threading or message updates
#
# Never blocks Claude — always exits 0.

EVENT_TYPE="${1:-unknown}"
WEBHOOK_URL="${CLAUDE_SLACK_WEBHOOK_URL:-}"
BOT_TOKEN="${CLAUDE_SLACK_BOT_TOKEN:-}"
CHANNEL="${CLAUDE_SLACK_CHANNEL:-}"

# Need at least one delivery method configured
[[ -z "$WEBHOOK_URL" && -z "$BOT_TOKEN" ]] && exit 0

# Per-project opt-in gate. The hook is installed globally in ~/.claude, so
# without this check credentials exported once in ~/.zshrc would fire on
# every Claude Code session — including personal or client projects unrelated
# to the team. When CLAUDE_SLACK_REPOS is unset, the hook is considered
# not-opted-in for this shell and exits silently even with credentials set.
# When set, the hook fires only for repos whose basename matches a
# comma-separated entry (case-sensitive, exact match after whitespace trim).
ALLOWED_REPOS="${CLAUDE_SLACK_REPOS:-}"
[[ -z "$ALLOWED_REPOS" ]] && exit 0

CURRENT_REPO="$(basename "$(git rev-parse --show-toplevel 2>/dev/null || pwd)")"
MATCHED=0
IFS=',' read -ra _REPOS <<< "$ALLOWED_REPOS"
for r in "${_REPOS[@]}"; do
  trimmed="$(printf '%s' "$r" | tr -d ' ')"
  [[ "$trimmed" == "$CURRENT_REPO" ]] && MATCHED=1 && break
done
[[ "$MATCHED" -ne 1 ]] && exit 0

# ---------- Parse stdin JSON ----------
INPUT=""
if ! read -t 0.5 -r -d '' INPUT 2>/dev/null; then
  # partial read is fine, INPUT has whatever was available
  true
fi

# Extract fields via jq (fail open if jq unavailable)
if command -v jq &>/dev/null && [[ -n "$INPUT" ]]; then
  SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // ""')
  HOOK_MESSAGE=$(echo "$INPUT" | jq -r '.message // ""')
  TRANSCRIPT_PATH=$(echo "$INPUT" | jq -r '.transcript_path // ""')
else
  SESSION_ID=""
  HOOK_MESSAGE=""
  TRANSCRIPT_PATH=""
fi

# ---------- Context gathering ----------
PROJECT_NAME="${PWD##*/}"
BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
TIMESTAMP=$(date -u +"%Y-%m-%d %H:%M UTC")

# Extract the user's original task from the transcript (first human message)
USER_TASK=""
if [[ -n "$TRANSCRIPT_PATH" ]] && [[ -f "$TRANSCRIPT_PATH" ]] && command -v jq &>/dev/null; then
  USER_TASK=$(jq -r '
    [.[] | select(.type == "human" or .role == "user")] | first |
    if .content then
      if (.content | type) == "string" then .content
      elif (.content | type) == "array" then
        [.content[] | select(.type == "text") | .text] | join(" ")
      else ""
      end
    else ""
    end
  ' "$TRANSCRIPT_PATH" 2>/dev/null || true)
  # Truncate to 200 chars for readability
  if [[ ${#USER_TASK} -gt 200 ]]; then
    USER_TASK="${USER_TASK:0:197}..."
  fi
fi

# Build display label and description from event type
case "$EVENT_TYPE" in
  notification)
    EVENT_LABEL="Needs Input"
    EVENT_EMOJI=":raised_hand:"
    if [[ -n "$HOOK_MESSAGE" ]]; then
      DESCRIPTION="$HOOK_MESSAGE"
    else
      DESCRIPTION="Claude Code is waiting for your input"
    fi
    ;;
  stop)
    EVENT_LABEL="Task Finished"
    EVENT_EMOJI=":white_check_mark:"
    DESCRIPTION="Claude Code has finished the task"
    ;;
  *)
    EVENT_LABEL="Event"
    EVENT_EMOJI=":large_blue_circle:"
    DESCRIPTION="Claude Code event: $EVENT_TYPE"
    ;;
esac

# ---------- Build message blocks ----------
# Summary line: show the user's original request when available
CONTEXT_LINE=""
if [[ -n "$USER_TASK" ]]; then
  # Escape special JSON characters in user task
  ESCAPED_TASK=$(echo "$USER_TASK" | jq -Rs '.' | sed 's/^"//;s/"$//')
  CONTEXT_LINE="\\n>:speech_balloon: _${ESCAPED_TASK}_"
fi

MESSAGE_TEXT="${EVENT_EMOJI} *Claude Code — ${EVENT_LABEL}*\\n*Repo:* \`${PROJECT_NAME}\`  *Branch:* \`${BRANCH}\`${CONTEXT_LINE}\\n${DESCRIPTION}\\n_${TIMESTAMP}_"

FALLBACK_TEXT="Claude Code [${EVENT_LABEL}]: ${PROJECT_NAME} (${BRANCH})"

# ---------- Helper: send via webhook (simple mode) ----------
send_webhook() {
  local payload="$1"
  local status
  status=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST -H "Content-type: application/json" \
    --max-time 5 --data "$payload" "$WEBHOOK_URL" 2>/dev/null) || true
  if [[ "$status" != "200" ]]; then
    MASKED_URL="...${WEBHOOK_URL: -6}"
    echo "notify-slack: webhook HTTP $status ($MASKED_URL)" >&2
  fi
}

# ---------- Helper: send via Slack Web API ----------
# Posts or updates a message. Outputs the message ts on success.
slack_api() {
  local method="$1"
  local payload="$2"
  local response
  response=$(curl -s -X POST \
    -H "Authorization: Bearer $BOT_TOKEN" \
    -H "Content-type: application/json; charset=utf-8" \
    --max-time 5 --data "$payload" \
    "https://slack.com/api/${method}" 2>/dev/null) || true
  if [[ -z "$response" ]]; then
    echo "notify-slack: empty API response for $method" >&2
    return 1
  fi
  local ok
  ok=$(echo "$response" | jq -r '.ok // false') || true
  if [[ "$ok" != "true" ]]; then
    local err
    err=$(echo "$response" | jq -r '.error // "unknown"') || true
    echo "notify-slack: $method failed: $err" >&2
    return 1
  fi
  echo "$response" | jq -r '.ts // ""'
}

# ---------- Session state (for threading) ----------
STATE_FILE=""
PARENT_TS=""
if [[ -n "$SESSION_ID" && -n "$BOT_TOKEN" ]]; then
  STATE_FILE="/tmp/claude-slack-${SESSION_ID}"
  if [[ -f "$STATE_FILE" ]]; then
    PARENT_TS=$(cat "$STATE_FILE" 2>/dev/null || true)
  fi
fi

# ---------- Delivery ----------
if [[ -n "$BOT_TOKEN" && -n "$CHANNEL" ]] && command -v jq &>/dev/null; then
  # ---- Web API mode: threading enabled ----
  BLOCKS=$(jq -n --arg text "$MESSAGE_TEXT" '[{
    "type": "section",
    "text": {"type": "mrkdwn", "text": $text}
  }]')

  if [[ -z "$PARENT_TS" ]]; then
    # First message for this session — becomes the parent
    PAYLOAD=$(jq -n \
      --arg channel "$CHANNEL" \
      --arg text "$FALLBACK_TEXT" \
      --argjson blocks "$BLOCKS" \
      '{channel: $channel, text: $text, blocks: $blocks}')
    TS=$(slack_api "chat.postMessage" "$PAYLOAD") || true
    # Save parent ts for future thread replies
    if [[ -n "$TS" && -n "$STATE_FILE" ]]; then
      echo "$TS" > "$STATE_FILE"
      PARENT_TS="$TS"
    fi
  else
    if [[ "$EVENT_TYPE" == "stop" ]]; then
      # Update the parent message with final status
      PAYLOAD=$(jq -n \
        --arg channel "$CHANNEL" \
        --arg ts "$PARENT_TS" \
        --arg text "$FALLBACK_TEXT" \
        --argjson blocks "$BLOCKS" \
        '{channel: $channel, ts: $ts, text: $text, blocks: $blocks}')
      slack_api "chat.update" "$PAYLOAD" >/dev/null || true
    fi

    # Post detail as a threaded reply
    PAYLOAD=$(jq -n \
      --arg channel "$CHANNEL" \
      --arg thread_ts "$PARENT_TS" \
      --arg text "$FALLBACK_TEXT" \
      --argjson blocks "$BLOCKS" \
      '{channel: $channel, thread_ts: $thread_ts, text: $text, blocks: $blocks}')
    slack_api "chat.postMessage" "$PAYLOAD" >/dev/null || true
  fi
else
  # ---- Webhook-only mode: individual messages with context ----
  PAYLOAD=$(jq -n \
    --arg text "$FALLBACK_TEXT" \
    --arg mrkdwn "$MESSAGE_TEXT" \
    '{text: $text, blocks: [{type: "section", text: {type: "mrkdwn", text: $mrkdwn}}]}')
  # Fallback if jq not available
  if [[ -z "$PAYLOAD" ]]; then
    PAYLOAD="{\"text\":\"${FALLBACK_TEXT}\"}"
  fi
  send_webhook "$PAYLOAD"
fi

# Never block Claude — always exit 0
exit 0
