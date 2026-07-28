---
name: shipped
description: Use when PRs have merged and the plan records need catching up — ticks every merged-but-unrecorded PR row (✅ + PR link) in the central plan issue, its build-plan artifact, and any cross-referenced issue, or invokes /shipped.
---

# Shipped

Say it after PRs land; the records catch up. **Bookkeeping only** — ticks and links:
never merges, never authors prose, never edits the plan (re-planning is
`/course-correct`'s job). Idempotent: running it twice in a row changes nothing, and a
merge missed last time is booked next time.

```
/shipped [--issue=N] [--pr=N]

  1. Find the plan issue and its artifact
  2. Compare the plan to GitHub          (merged but unticked)
  3. Tick the issue rows
  4. Tick the artifact
  5. Tick cross-referenced issues
  6. Report
```

No gates: invoking the skill is the permission. Write, then report.

## Phase 1 — Find the records

**The plan issue**, in order:

1. `--issue=N`.
2. The issue the anchor PR references — `--pr=N`, else the PR of the branch you're on
   or the one just discussed; read its body and branch name.
3. The conversation — the last `PRD published: ... (issue #N)` line.
4. A repo scan — open issues whose body carries a `## PR breakdown` section or a table
   of PR rows.
5. Ask.

Confirm an auto-detected number before writing to it.

**The artifact**: read `<!-- build-plan:artifact url=... -->` from the issue body. No
marker → list the user's artifacts and match a title to this repo and goal (the shapes
in the wild: `<goal>, one small PR at a time`, `<repo> — PR map`, `<goal> — Build
Plan`); after Phase 4 succeeds, write the marker into the issue so later runs skip the
search. No confident title match, or no Artifact tool (headless) → skip Phase 4 and say
so in the report.

## Phase 2 — Compare the plan to GitHub

List the repo's PRs once — `gh pr list --state all -L 200 --json
number,title,state,headRefName,url` — then walk the plan's PR rows. A row matches a PR
by, in order: the `#NN` it already records → a head branch carrying the row's id
(`2.3`, `B3`) → an unambiguous title match. The work list is every row whose PR is
`MERGED` but whose row isn't ticked yet.

A merged PR that names the plan but matches no row, or matches two → the report, never
a guess. Already-ticked rows are skipped untouched — that is the idempotency.

## Phase 3 — Tick the issue rows

Flip only the matched rows, in the issue's own style — mirror how its already-done rows
look, never introduce a new format:

- a Status column → `Merged #NN` (linked)
- a ✅-prefix style → `✅` beside the row id, linked `#NN` where the siblings put it
- a Shipped column → `✅ [#NN](<url>)`

A slice or section heading gains `— ✅ **DONE**` only when every row under it is ticked
**and** sibling headings already use that convention.

Rebuild the body with the Write tool and `gh issue edit N --body-file` — cells carry
backticks and `$` a heredoc would interpolate. Nothing changes but the ticked cells
(plus the artifact marker from Phase 1, once).

## Phase 4 — Tick the artifact

Fetch the live page (WebFetch on the artifact URL), then make the smallest edits that
make it true — keep its classes, structure, and design; never regenerate it from a
template:

- the merged PR's chip/card → the page's own done state, plus the PR link where its
  cards carry links
- rows whose blockers are now all done lose their blocked state (→ the page's
  ready/next state)
- header stats and counters ("12 / 20 landed") → recount

Republish with the Artifact tool to the same URL.

## Phase 5 — Tick cross-referenced issues

Issues the merged PRs or the ticked rows explicitly reference (hand-off issues, module
trackers): search each for a row or checkbox naming the merged PR or its row id, and
apply the same tick with the same style-mirroring discipline. Only the cell that names
the work — never any other line of that issue.

## Phase 6 — Report

```
Shipped: <k> PRs booked — issue #N (<row ids>), artifact updated (<x/y landed>), <m> cross-refs
Unmatched: <#NN — why it didn't book> (or none)
```

Plus anything skipped (no artifact, headless) and the marker URL if newly pinned.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Writing evidence prose into a cell | Ticks and links only — the PR flow owns the story |
| Regenerating the artifact page | Surgical edits to the live page, same classes |
| Guessing an ambiguous PR→row match | Put it in the report instead |
| Heredoc for the issue body | Write tool + `--body-file` — cells carry backticks and `$` |
| Reformatting rows while ticking | Mirror the issue's existing style; a re-run must be a no-op |
