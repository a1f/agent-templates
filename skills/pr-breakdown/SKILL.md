---
name: pr-breakdown
description: Use when a PRD issue's slice plan needs breaking into small ~100-200 LOC pull requests recorded as sub-rows in that issue, or invokes /pr-breakdown.
---

# PR Breakdown

Break the slice plan in a PRD issue into **small PRs (~100–200 LOC, excluding
tests)**, recorded as sub-rows in the **same issue**.

```
/pr-breakdown [--issue=N]

  1. Find the issue and slice plan
  2. Split each slice into PRs
  3. Show it, wait for approval   (gate)
  4. Append to the SAME issue
```

## Phase 1 — Find the issue and slice plan

Use `--issue=N` if given. Otherwise scan the conversation for the last
`PRD published: ... (issue #N)` line; if there's none, ask. If you auto-detected
it, confirm the number with the user. Read the body. If it has no `## Build plan`
section, **stop** and tell the user to run `/to-issues` first — don't invent a
breakdown. If the Build plan says `No slicing — single PR`, emit one
`### Slice 1 — <name> (1 PR)` row (derive `<name>` from the PRD's *What we're
building*) and skip to Phase 3.

## Rules for splitting

- 100–200 LOC per PR, excluding tests. Over ~200 → split further; a tiny slice may be one PR.
- One cohesive, reviewable, demoable change per PR.
- Foundations first: reusable primitives before the PRs that wire them up.
- Note where PRs in a slice run in parallel.
- **Rows only.** Do NOT write coder prompts (module boundary, acceptance criteria, etc.) — those are generated later, one PR at a time.

## Phase 2 — Draft sub-rows

Derive each `<name>` from the slice's `What`.

```markdown
## PR breakdown

### Slice <n> — <name> (<k> PRs)
| PR | What | LOC | Done when |
|----|------|-----|-----------|
| n.1 | ... | ~150 | <observable result> |
| n.2 | ... | ~120 | ... |

*n.1 ∥ n.2 (independent)*
```

End with **Estimated total: ~N PRs.**

## Phase 3 — Approve (gate)

Show the full breakdown in chat. **Wait for approval or edits** before touching
the issue.

## Phase 4 — Append to the same issue

Keep canonical order PRD → `## Build plan` → `## PR breakdown`: replace the PR
breakdown in place, preserving everything above it. The rebuild keys on the exact
`## PR breakdown` heading; `tr -d '\r'` guards CRLF; abort on an empty read:

```bash
ISSUE=<the issue number>; NEW=$(mktemp)
# ...write the new "## PR breakdown" section to "$NEW"...
CUR=$(gh issue view "$ISSUE" --json body -q .body | tr -d '\r')
[ -n "$CUR" ] || { echo "abort: empty issue body" >&2; exit 1; }
HEAD=$(printf '%s\n' "$CUR" | awk '/^## PR breakdown/{exit} {print}')
OUT=$(mktemp)
{ printf '%s\n\n' "$HEAD"; cat "$NEW"; } > "$OUT"
gh issue edit "$ISSUE" --body-file "$OUT"
rm -f "$NEW" "$OUT"
echo "PR breakdown appended to issue #$ISSUE"
```
