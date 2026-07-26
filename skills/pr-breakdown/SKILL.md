---
name: pr-breakdown
description: Use when a PRD issue's slice plan needs breaking into small pull requests (~35 counted lines each, tests excluded) recorded as a table in that same issue and drawn as a private claude.ai PR-map artifact, or invokes /pr-breakdown.
---

# PR Breakdown

Break the slice plan in a PRD issue into **small PRs (~35 counted lines each)** and
keep two views of them: a **table** in the same issue, one row per PR, and a **PR
map** — a private claude.ai artifact laying the PRs out as waves, with blocked-by edges
and a card per PR.

**The table is the source of truth** — the map is drawn from it every run. **Status comes
from GitHub** — the table caches each PR's `#NN` and the state it last saw.

```
/pr-breakdown [--issue=N]

  1. Read the issue — plan, existing rows, existing map
  2. Write the PR rows
  3. Discuss and approve        (gate)
  4. Draw and publish the map
  5. Write it back to the issue
```

## Phase 1 — Read the issue

Use `--issue=N` if given; else scan the conversation for the last
`PRD published: ... (issue #N)` line, or ask. Confirm an auto-detected number. Read the
body with `gh issue view N --json body -q .body`.

No `## Build plan` section → **stop** and tell the user to run `/to-issues` first.

The slices are that section's table: each row's *What* and *Blocked by* seed the PRs, its
*Demoable as* seeds their `Done when`, and its *Mode* (`AFK` / `HITL`) says whether it
needs the human. `No slicing — single PR` instead of a table means one slice, one PR.

From an existing `## PR breakdown`, keep two things: **the rows** (Phase 2 builds on them)
and **the map URL** in `<!-- pr-breakdown:map url=<url> -->` (Phase 4 updates that same
artifact).

## Phase 2 — Write the PR rows

Split each slice into PRs — one cohesive, reviewable, demoable change each, foundations
before the PRs that use them. **Budget each PR at ~35 counted lines** — added lines
excluding tests, lockfiles, and generated output, with prose (`.md`, docs) counted apart.
A PR the size gate will not pass is a PR you must split now: **over 50 counted lines is
unlandable once it touches 3+ files, over 100 on 1–2 files, over 150 of prose.** Estimate
high: a row you guess at 40 lands at 60. More, smaller rows are always the right answer. **Rows only**: no coder
prompts (module boundaries, acceptance criteria) — those come later, one PR at a time.

```markdown
### Slice 1 — <name> (2 PRs)
| PR | What | LOC | Blocked by | Status | Done when |
|----|------|-----|-----------|--------|-----------|
| 1.1 | ... | ~30 | — | Todo | <observable result> |
| 1.2 | ... | ~35 | 1.1 | Todo | ... |
```

Close the tables with `**Estimated total:** ~P PRs · W waves.`

- **Blocked by** — the `n.k` ids this PR needs merged first, from any slice, or `—`. Must
  be acyclic; it is the only dependency record, and the waves come from it.
- **Status** — `Todo` · `In review #NN` · `Merged #NN` · `Closed #NN`. Nothing upstream
  writes this, so match the rows against the repo's PRs yourself — list them once with
  `gh pr list --state all -L 200 --json number,title,state,headRefName`, then match each
  row by its recorded `#NN`, else by a head branch carrying its `n.k` id, else by an
  unambiguous title match. Record the number the first time it matches and set the word
  from `state`. No `gh`, or no confident match → leave the row as it is.
- **Gate PR** — validation machinery that blocks merging (CI, image, deploy, e2e). Start
  its *What* with `Gate:`; the map styles it from that.

**On a re-run, the existing table wins.** Keep every row and cell, refresh Status, and add
rows only for a slice that has none yet. Removing or re-scoping rows is `/course-correct`'s
job, so its edits survive the redraw.

**Waves** group the *Blocked by* graph: a PR sits one column right of its latest blocker,
so nothing in a wave blocks anything else in it. A cycle → stop and report it.

## Phase 3 — Discuss and approve (gate)

Show the tables and the waves in chat. **Wait for approval or edits before touching the
issue or publishing anything.**

## Phase 4 — Draw and publish the map

Fill `~/.claude/at/templates/pr-breakdown-map.html` (or the repo's copy at
`templates/pr-breakdown-map.html`). It carries the design, the classes, and — in its
`SLOT` comments — how chips and cards are wired; mirror its example markup and keep its
class names. Write the filled page to the session scratch directory, never the target
repo, as `pr-map-<owner>-<repo>-<issue>.html` (`gh repo view --json owner,name`, owner is
`.owner.login`).

Neither copy present — the staged extra lags a reinstall — → **skip the map, don't
hand-roll one**: go straight to Phase 5 so the table still lands, and tell the user to
reinstall the `pr-breakdown` package to get it back.

What you supply:

- **Header** — `owner/repo · issue #N`, a title (`<goal>, one small PR at a time`), a
  paragraph on the plan, and stats: PRs merged `x / y`, ~LOC per PR, wave count, and how
  many slices need the human.
- **Lanes** — one per wave, left to right, named for what the wave unlocks ("The seed",
  "Fan out"). Every chip carries `data-deps` naming its blockers; the page's own script
  draws the edges from those, so never hand-author edge SVG.
- **Cards** — one per PR, grouped into a section per wave: what it does in plain words,
  why it's scoped that way if that isn't obvious, its blockers, its `Done when`, its LOC,
  and a link to the PR once merged.
- **Status → class** — on the chip, and on its card:

  | Status | chip | card |
  |--------|------|------|
  | Merged | `done` | `donecard` + `tag done` |
  | In review | `active` | `tag active` |
  | Closed | `closed` | `tag closed` |
  | Todo, still blocked | `blocked` | — |
  | Todo, ready | — | — |

  A gate adds `gate` / `gatecard` / `tag gate` on top. A `HITL` slice gets an
  `<span class="adot"></span>` on its first chip and a `needs you` tag on that card.

Publish with the Artifact tool — title `<repo> — PR map`, favicon `🗺️`, one-sentence
description. Reuse the Phase 1 map URL as the `url` parameter so the same artifact
updates; if that fails, publish fresh and record the new link. No Artifact tool
(headless) → skip it, keep any existing link, and say so in the report.

## Phase 5 — Write it back to the issue

`## PR breakdown` is the issue's last section (PRD → `## Build plan` → `## PR breakdown`;
a `## Status` block from course-correct may sit above the PRD and is preserved). This
skill owns that section whole and rewrites it as: the heading, the map marker, a visible
`🗺️ [PR map](url)` line, then the tables. With no URL, drop the marker and the link rather
than emitting an empty one.

**Write the section with the Write tool, not a heredoc** — *What* and `Done when` cells
carry backticks and `$` that a heredoc would interpolate into the issue.

```bash
ISSUE=<the issue number>; NEW=<the section file you just wrote>
BODY=$(gh issue view "$ISSUE" --json body -q .body | tr -d '\r')
[ -n "$BODY" ] || { echo "abort: empty issue body" >&2; exit 1; }
[ -s "$NEW" ]  || { echo "abort: empty new section" >&2; exit 1; }
HEAD=$(printf '%s\n' "$BODY" | awk '/^## PR breakdown/{exit} {print}')
TAIL=$(printf '%s\n' "$BODY" | awk '/^## PR breakdown/{b=1;next} b&&/^## /{b=0;t=1} t')
OUT=$(mktemp)
{ printf '%s\n\n' "$HEAD"; printf '%s\n' "$(cat "$NEW")"; [ -n "$TAIL" ] && printf '\n%s\n' "$TAIL"; } > "$OUT"
gh issue edit "$ISSUE" --body-file "$OUT" \
  && rm -f "$OUT" \
  && echo "PR breakdown appended to issue #$ISSUE"
```

`$NEW` must start with the `## PR breakdown` heading — `HEAD` stops before it, so without
it the next run can't find the section and appends a duplicate.

## Report

End with `PR breakdown appended to issue #N`, then the map URL, the PR and wave counts,
and anything you carried forward or couldn't refresh.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Hand-authoring the edge SVG | Leave `<svg class="edges">` empty — the page's script draws edges from `data-deps` |
| Rebuilding rows from the Build plan on a re-run | The table wins; keep every cell and only add what's missing |
