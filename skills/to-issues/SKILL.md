---
name: to-issues
description: Use when a PRD issue needs breaking into vertical, tracer-bullet slices recorded as a table in that same issue, or invokes /to-issues.
---

# To Issues

Break a PRD issue into **vertical, tracer-bullet slices** — each a narrow but
COMPLETE path through every layer it touches (schema, API, UI, tests), demoable on
its own — recorded as one growing table inside the same issue, never fanned out.
Prefer many thin slices over a few thick ones; order them thinnest-first.

```
/to-issues [--issue=N]

  1. Find the issue and read it
  2. Draft slices + parallelization
  3. Discuss and refine          (gate)
  4. Append the plan to the SAME issue
```

## Phase 1 — Find the issue

Use `--issue=N` if given. Otherwise scan the conversation for the last
`PRD published: ... (issue #N)` line; if there's none, ask. If you auto-detected
it, confirm the number with the user. Read the body; use the codebase's own
vocabulary; respect ADRs.

## Phase 2 — Draft slices

Each slice carries a **Demoable as** line (how you'd demo or verify it — if you
can't write one, it isn't end-to-end), a **Mode** (`AFK` = an agent runs it alone;
`HITL` = needs the user: design taste, UX, a judgment call), a **Size** (`S`/`M`/`L`,
a rough feel — real LOC come in pr-breakdown), and **Blocked by**.

```markdown
## Build plan — vertical slices

| # | What | Demoable as | Mode | Size | Blocked by |
|---|------|-------------|------|------|------------|
| 1 | ... | ... | AFK | M | — |

### Parallelization

| Wave | Runs together | Notes |
|------|---------------|-------|
| 0 | 1 | foundation |
| 1 | 2 + 3 | independent |

**Critical path:** 1 → 2 → ...
```

Waves are a topological grouping of `Blocked by`: same-wave slices share no
blocking relationship. If the work has **no real slices** (e.g. one tiny change),
say so — and still write the `## Build plan — vertical slices` heading with a
single line, `No slicing — single PR`, so the next phase proceeds.

## Phase 3 — Discuss (gate)

Present the slices as a numbered list, then ask the user:

- Is the **granularity** right — too coarse, too fine?
- Are the **dependencies** correct?
- **Merge or split** any (e.g. an `L` slice worth splitting)?
- Are the **HITL/AFK** calls right?

Iterate until they approve. **Don't touch the issue until then.** With no real
slices, skip these questions — just confirm the single-PR plan.

## Phase 4 — Append to the same issue

The issue stays in canonical order: PRD → `## Build plan` → `## PR breakdown`.
Rebuild it from those parts so a re-run replaces the Build plan in place — never
duplicating or reordering. The rebuild keys on those exact headings (so don't use
them in PRD prose); `tr -d '\r'` guards CRLF; abort if the read comes back empty:

```bash
ISSUE=<the issue number>; NEW=$(mktemp)
# ...write the new "## Build plan — vertical slices" + "### Parallelization" to "$NEW"...
BODY=$(gh issue view "$ISSUE" --json body -q .body | tr -d '\r')
[ -n "$BODY" ] || { echo "abort: empty issue body" >&2; exit 1; }
HEAD=$(printf '%s\n' "$BODY" | awk '/^## Build plan/{exit} /^## PR breakdown/{exit} {print}')
PRS=$(printf '%s\n' "$BODY"  | awk '/^## PR breakdown/{f=1} f')
OUT=$(mktemp)
{ printf '%s\n\n' "$HEAD"; printf '%s\n' "$(cat "$NEW")"; [ -n "$PRS" ] && printf '\n%s\n' "$PRS"; } > "$OUT"
gh issue edit "$ISSUE" --body-file "$OUT"
rm -f "$NEW" "$OUT"
echo "Slices appended to issue #$ISSUE"
```

If a `## PR breakdown` already existed, warn the user it may now be stale and
suggest re-running `/pr-breakdown`.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Horizontal layers (all schema, then all API) | Each slice goes end-to-end |
