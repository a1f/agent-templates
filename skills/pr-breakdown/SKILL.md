---
name: pr-breakdown
description: Use when a PRD issue's slice plan needs breaking into small ~100–200 LOC pull requests recorded as a table in that same issue and drawn as a private claude.ai PR-map artifact, or invokes /pr-breakdown.
---

# PR Breakdown

Break the slice plan in a PRD issue into **small PRs (~100–200 LOC, excluding
tests)**, recorded two ways: a table in the same issue — one row per PR — and a PR map,
a private claude.ai artifact laying the PRs out as waves, with blocked-by edges and one
card per PR.

**The table is authoritative for the rows** — the map is a projection of it, re-rendered
every run. **Status is GitHub's** — the table caches each PR's `#NN` and the state it
last saw.

```
/pr-breakdown [--issue=N]

  1. Find the issue, slice plan, and existing breakdown
  2. Draft / reconcile the PR rows (blocked-by + status)
  3. Discuss and approve                    (gate)
  4. Fill the map template from the rows
  5. Publish / update the artifact
  6. Write table + map link to the SAME issue
```

## Rules for splitting

- Over ~200 LOC → split further.
- One cohesive, reviewable, demoable change per PR.
- Foundations first: reusable primitives before the PRs that wire them up.
- **Blocked by** — the only dependency record: an *acyclic* list, at PR grain, of the
  `n.k` ids a PR needs merged first (finer than the slice's own *Blocked by*).
- **Rows only.** No coder prompts (module boundary, acceptance criteria, …) —
  generated later, one PR at a time.

## Phase 1 — Find the issue, slice plan, and existing breakdown

Use `--issue=N` if given. Otherwise scan the conversation for the last
`PRD published: ... (issue #N)` line; if there's none, ask. Confirm an auto-detected
number. Read the body (`gh issue view N --json body -q .body`).

- No `## Build plan — vertical slices` section → **stop**; tell the user to run
  `/to-issues` first.
- `No slicing — single PR` under it → treat it as slice 1 with one PR `1.1` (no
  *Mode*; the map's wave name is the goal). Its *What* and `Done when` come from the PRD's
  *What we're building* and acceptance; `Blocked by` `—`, `Status` `Todo`.

Otherwise the slices are the `## Build plan — vertical slices` table to-issues wrote —
each row's *What* and *Blocked by* seed the PRs, and its *Mode* (`AFK` / `HITL`) marks
whether the slice needs the human.

From any existing `## PR breakdown`, capture what a re-run preserves:

- **The rows.** Carry every cell forward — Phase 2 reconciles.
- **The map URL** in `<!-- pr-breakdown:map url=<url> -->`. Reuse it in Phase 5 so the
  same artifact updates instead of a new one appearing.

## Phase 2 — Draft / reconcile the PR rows

**First run (no table)** — split each Build-plan slice into PRs, `<name>` from its
*What*, each PR's `Done when` a checkable outcome drawn from the slice's *Demoable as*.
One table per slice:

```markdown
### Slice 1 — <name> (2 PRs)
| PR | What | LOC | Blocked by | Status | Done when |
|----|------|-----|-----------|--------|-----------|
| 1.1 | ... | ~120 | — | Todo | <observable result> |
| 1.2 | ... | ~140 | 1.1 | Todo | ... |
```

**Re-run (table exists)** — match rows to slices by slice number (its `### Slice n`
heading, stable across renames), keep every row and cell, and change only:

- refresh each `#NN` row's Status (below);
- add rows for a Build-plan slice not yet represented.

Removing a dropped slice's rows, or growing a slice's PRs, is `/course-correct`'s job —
so its edits survive this redraw.

Close the tables with **Estimated total:** ~P PRs · W waves.

- **Status** — `Todo` · `In review #NN` · `Merged #NN` · `Closed #NN`. make-pr /
  pr-babysit stamp a row's `#NN` when the PR opens. When `gh` is available, for each row
  carrying a `#NN` run
  `gh pr view NN --json state -q .state` and rewrite the word, keeping the `#NN`: `MERGED`
  → `Merged`, `OPEN` → `In review`, `CLOSED` (unmerged) → `Closed`; a missing `gh` or a
  failed call → keep the recorded value. New rows are `Todo`. Discovering *unrecorded* PRs
  is `/course-correct`'s job.
- **Gate PRs** — validation machinery that blocks merging (a CI / image / deploy / e2e
  gate). Start its *What* with `Gate:` (e.g. `Gate: delivery contract`); the map keys on
  that prefix, so nothing else needs a column.

**Waves** — a topological grouping of the *Blocked by* graph (0-indexed): a PR sits one
column right of its latest blocker (a no-blocker PR is Wave 0), so no same-wave PR blocks
another. Same-wave PRs are the map's columns. A cycle → stop and report it; don't guess a
layering.

## Phase 3 — Discuss and approve (gate)

Show the full breakdown in chat — the per-slice tables plus the derived wave list. **Wait
for approval or edits before touching the issue.**

## Phase 4 — Fill the map template

**Template**: `~/.claude/at/templates/pr-breakdown-map.html` (staged), else the repo's
`templates/pr-breakdown-map.html`; only if neither exists, hand-author a single-file page
on the same contract. It owns the tokens, the class *definitions*, and — in its `SLOT`
comments — the structural fill rules (`data-id` / `data-deps` / `href` / slug / id); this
skill owns the status classes and the adot (below).

Write the filled page to the session scratch directory (never the target repo) as
`pr-map-<owner>-<repo>-<issue>.html` — owner/repo from `gh repo view --json owner,name`
(owner is `.owner.login`), or the issue number alone if that fails.

Fill the `SLOT` comments by mirroring the template's example markup, supplying (every id
— `data-id`, `data-deps`, `href`, `after:` — is the `n.k` hyphen-slugged, `1.2` → `1-2`):

- **Header** — an eyebrow `owner/repo · issue #N`; a page heading `<goal>, one small PR
  at a time` (`<goal>` from the PRD's *What we're building*); a one-paragraph plan
  summary; four `.stat` blocks: PRs merged `x / y` (x = `Merged` rows, y = all rows), ~LOC
  per PR (mean over all rows), `W` waves, `needs you` (pending HITL slices — a slice is
  *pending* while its **lead PR**, its smallest `n.k`, is neither `Merged` nor `Closed`).
- **Lanes** — one `.lane` per wave, left to right; set the lane grid to `repeat(W, 1fr)`;
  label each wave for the slice of its earliest PR (the single-PR plan's one wave is the
  goal).
- **Status → class** — on the PR's chip, its card, and the card's status `tag` (class · text):

  | Status | chip | card | tag |
  |--------|------|------|-----|
  | Merged | `done` | `donecard` | `tag done` · merged |
  | In review | `active` | — | `tag active` · in review |
  | Closed | `closed` | — | `tag closed` · closed |
  | Todo, a blocker unmerged | `blocked` | — | — |

  A ready Todo takes no status class. A gate adds `gate` / `gatecard` / `tag gate` · gate,
  composed with the row above (e.g. `class="chip gate done"`). Each *pending* `HITL` slice
  gets an `<span class="adot"></span>` on its lead-PR chip and a
  `<span class="tag you">needs you</span>` on that card. The template legend echoes these
  status words and the adot rule — keep them in step if you rename either.
- **Cards** — group them into one `.wave` section per wave, same order as the lanes: its
  `<h2>` is the wave name and its `.sub` a one-line summary of what the wave unlocks.
- **Text** — per card:
  - the *What* as a plain-sentence card `<p>`, plus a short title distilled from it for
    the chip `.n` and card `<h3>`
  - the LOC in `<span class="tag size">`
  - an `after:` line linking each blocker's card by hyphen id (`#<slug>`, e.g. `#1-2`),
    omitted when none
  - the row's `Done when` as the `Done when` list, one `<li>` per outcome
  - an `.ev` line to `https://github.com/<owner>/<repo>/pull/NN`, only when `Merged`
  - optional: a `p.why` (why the PR is scoped this way)
- **Map hint** — optionally fill the page-level `.map-hint` with the critical path
  (e.g. `1.1 → 1.2 → 2.1`).

## Phase 5 — Publish / update the artifact

Publish with the Artifact tool: title `<repo> — PR map`, favicon `🗺️` (stable across
reruns), a one-sentence description. The template embodies the design — no need to load
`artifact-design`.

- Same conversation → republish the same file path (keeps the URL).
- Later session → pass the Phase 1 map URL as the `url` parameter so the same artifact
  updates. Fails (deleted or not owned) → publish without `url`; Phase 6 records the new
  link.
- Artifact tool unavailable (headless/CI) → skip publishing; Phase 6 writes the tables
  with the existing URL if there is one, else no map link, and the report says the map
  wasn't refreshed.

## Phase 6 — Write to the same issue

`## PR breakdown` is the last canonical section — PRD → `## Build plan` →
`## PR breakdown`. A `## Status` block from course-correct may precede the PRD and is
kept, so don't use those headings in PRD prose. This skill owns the section whole:
regenerate it as the `## PR breakdown` heading, the `<!-- pr-breakdown:map url=… -->`
marker, the visible `🗺️ [PR map](url)` line, the per-slice tables, and the Estimated-total
line.

- **No resolved URL** — omit both the marker and the map line; never an empty `()`.
- **Author `$NEW` with the Write tool, not an inline heredoc** — *What* / `Done when`
  cells carry backticks and `$` a heredoc would interpolate. It starts with the
  `## PR breakdown` heading (HEAD stops before it, or the next re-run's `awk` duplicates
  the section).

The rebuild keys on that heading; `tr -d '\r'` guards CRLF; a TAIL after the section is
preserved; it aborts on an empty read:

```bash
ISSUE=<the issue number>; NEW=<the section file you wrote with the Write tool>
BODY=$(gh issue view "$ISSUE" --json body -q .body | tr -d '\r')
[ -n "$BODY" ] || { echo "abort: empty issue body" >&2; exit 1; }
[ -s "$NEW" ] || { echo "abort: empty new section" >&2; exit 1; }
HEAD=$(printf '%s\n' "$BODY" | awk '/^## PR breakdown/{exit} {print}')
TAIL=$(printf '%s\n' "$BODY" | awk '/^## PR breakdown/{b=1;next} b&&/^## /{b=0;t=1} t')
OUT=$(mktemp)
{ printf '%s\n\n' "$HEAD"; printf '%s\n' "$(cat "$NEW")"; [ -n "$TAIL" ] && printf '\n%s\n' "$TAIL"; } > "$OUT"
gh issue edit "$ISSUE" --body-file "$OUT" \
  && rm -f "$NEW" "$OUT" \
  && echo "PR breakdown appended to issue #$ISSUE"
```

## Report

End with `PR breakdown appended to issue #N`, then: the map URL (or that it wasn't
refreshed, and why), the PR / wave counts, and any statuses carried forward.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Authoring the edge SVG yourself | Leave `<svg class="edges">` empty — the inline script draws every edge from `data-deps` |
