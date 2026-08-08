---
name: to-prd
description: Use when the user wants to turn the current conversation into a short, human-readable PRD published as a GitHub issue, or invokes /to-prd.
---

# To PRD

Turn the conversation and codebase into a **short PRD a human actually reads**,
then publish it as a GitHub issue.

```
/to-prd [--title="..."] [--label=Plan] [--issue=N]

  1. Gather context (conversation + light repo read)
  2. Clarify gaps via AskUserQuestion   (gate, only if thin)
  3. Draft the PRD
  4. Show it, wait for approval          (gate)
  5. Publish the issue; print URL + number
```

## Arguments

| Arg | Default | Notes |
|-----|---------|-------|
| `--title="..."` | Derived from context | Issue title |
| `--label=...` | `Plan` | Dropped if the repo has no such label; pass `--label=` for none |
| `--issue=N` | Create new | Re-publish: replace the PRD, keep any appended slices/PRs |

## Phase 1 — Gather context

Read the conversation; explore the repo only if you haven't. Use the codebase's
own vocabulary and respect existing ADRs.

## Phase 2 — Clarify (gate)

If a fact that changes the design is missing, ask with **AskUserQuestion** (≤4 at
a time, concrete options) — otherwise skip when context is rich.

## Phase 3 — Draft

**Write it tight:**

- One screen. Cut anything that doesn't change a decision.
- The `english` rule governs every line — it loads each session, so you already have it. Cut all hedging.
- Tables and bullets over paragraphs. A PRD is scanned, not read: this is the one document where a list beats prose.
- Only what was discussed or confirmed — invent nothing.
- No file paths or code; they rot. Rare exception: a tiny snippet that nails a decision — a type, a schema.

**Use these sections:**

```markdown
## The problem
<What's wrong today, in the reader's words. One short paragraph.>

## What we're building
<A few sharp sentences. The core idea.>

## How it works
<The key mechanics as bullets.>

## Decisions already made
<Table: Area | Choice.>

## In scope / Out of scope
<Two short lists.>

## Open questions
<What still needs the user's call. Omit if none.>
```

## Phase 4 — Approve (gate)

Show the draft in chat. Wait for an OK or edits. **Don't publish until approved.**

## Phase 5 — Publish

Write the approved body to a temp file, which dodges shell-escaping. Drop an unknown
label so the create can't fail on it. Then print one parseable line:

```bash
TITLE="..."; LABEL="${LABEL-Plan}"; BODY=$(mktemp)
# ...write the approved PRD to "$BODY"...
[ -n "$LABEL" ] && { gh label list --json name -q '.[].name' | grep -Fqx "$LABEL" || LABEL=""; }
URL=$(gh issue create --title "$TITLE" ${LABEL:+--label "$LABEL"} --body-file "$BODY")
rm -f "$BODY"
[ -n "$URL" ] || { echo "abort: issue create failed" >&2; exit 1; }
echo "PRD published: $URL (issue #${URL##*/})"
```

For `--issue=N`, replace only the PRD and keep the downstream sections in place.
The rebuild keys on the exact `## Build plan` / `## PR breakdown` headings (so
never use those headings in PRD prose); `tr -d '\r'` guards CRLF:

```bash
ISSUE=<the issue number>; BODY=$(mktemp)
# ...write the approved PRD to "$BODY"...
CUR=$(gh issue view "$ISSUE" --json body -q .body | tr -d '\r')
[ -n "$CUR" ] || { echo "abort: empty issue body" >&2; exit 1; }
DOWN=$(printf '%s\n' "$CUR" | awk '/^## Build plan/{f=1} /^## PR breakdown/{f=1} f')
OUT=$(mktemp)
{ printf '%s\n\n' "$(cat "$BODY")"; [ -n "$DOWN" ] && printf '%s\n' "$DOWN"; } > "$OUT"
gh issue edit "$ISSUE" --body-file "$OUT"
rm -f "$BODY" "$OUT"
echo "PRD published: $(gh issue view "$ISSUE" --json url -q .url) (issue #$ISSUE)"
```
