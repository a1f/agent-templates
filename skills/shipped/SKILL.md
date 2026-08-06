---
name: shipped
description: Use when PRs have merged and the plan records need catching up — ticks every merged-but-unrecorded PR row (✅ + PR link) in the central plan issue, its build-plan artifact, and any cross-referenced issue, or invokes /shipped.
---

# Shipped

Say it after PRs land; the records catch up. **Bookkeeping only** — ticks and links:
never merges, never authors prose, never edits the plan (re-planning is
`/course-correct`'s job). Idempotent: a re-run changes nothing, and whatever a prior
run missed is booked next time.

```
/shipped [--issue=N] [--pr=N]

  1. Find the records            (plan issue + its artifact)
  2. Compare the plan to GitHub  (merged but unbooked)
     ├─ issue lane      3. Tick the issue rows → 5. Tick cross-referenced issues
     └─ artifact lane   4. Tick the artifact
     join               pin the artifact marker, report
```

**No approval gates** — never preview or confirm an edit; invoking the skill is the
permission. `--pr` (or the branch you're on) only seeds discovery — every run still
reconciles **all** merged-but-unbooked rows.

## Phase 1 — Find the records

**The plan issue**, in order:

1. `--issue=N`.
2. The issue the anchor PR references — `--pr=N`, else the current branch's PR or the
   one just discussed; read its body for the issue link (several plan-issue links
   count as several candidates).
3. The conversation — the last `PRD published: ... (issue #N)` line.
4. A repo scan — issues (open, else recently closed) whose body carries a
   `## PR breakdown` section or a table whose rows describe one PR each.

Never pause to confirm a detection — verify it instead, pulling Phase 2's PR listing
forward: at least one row records or matches a PR of this repo. A plan recording no PR
at all yet qualifies only through steps 1–2, where the user or a PR pointed at it. A failed check on an auto-detected issue
(steps 2–4) falls through to the next step; an explicit `--issue` or `--pr` that fails
to resolve — or whose issue fails the check — **stops the run and reports**, never
falling through past the user's word. More than one issue qualifies, or all four
steps come up dry → ask; headless (no interactive user to ask, e.g. a scheduled run),
stop and report with nothing written.

**The artifact**, in order:

1. The issue's marker — `<!-- shipped:artifact url=... -->` (this skill's own pin)
   wins over `<!-- pr-breakdown:map url=... -->` (that skill's record; a page found
   through it needs no new pin).
2. A marker is **stale** when its page can't be fetched, isn't this plan's page, or
   its line appears more than once (either kind). Stale or absent → match a title from
   the user's artifact list to this repo and the plan's goal — the shapes in the wild:
   `<goal>, one small PR at a time`, `<repo> — PR map`, `<goal> — Build Plan`.
3. Skip Phase 4 — don't dispatch the artifact lane — saying so in the report, on any
   of: no confident title match; several matches (a guess would pin the wrong page);
   no Artifact tool; a headless run. Phase 4 adds the runtime skips: a failed fetch,
   markup that isn't the page's source, a refused or URL-changing republish.

## Phase 2 — Compare the plan to GitHub

Read the body once into the session scratch directory and work from that copy — it is
also Phase 3's mid-run baseline (`sed -e 's/\r$//'` — strip line-ending CRs only, so
mid-line CRs survive):

```bash
ISSUE=<the issue number>; SCRATCH=<the session scratch directory>
gh issue view "$ISSUE" --json body -q .body | sed -e 's/\r$//' > "$SCRATCH/old-body.md"
```

Reuse Phase 1's PR listing — `gh pr list --state all -L 1000 --json
number,title,state,headRefName,url`. A row is **booked** when its status records the
merge — ✅ / `Merged` / a checked box — **with** a linked `#NN`; a tick missing its
link joins the work list for link repair alone. Rows tracking another repo
(`owner/other#NN` or a foreign URL) never match — list the unbooked ones under the
report's Skipped line. A local row matches a PR by, in order:

1. the `#NN` or same-repo URL it already records — absent from the listing → check it
   directly with `gh pr view <NN>` before calling it unfindable;
2. a head branch carrying the row's id (`2.3`, `B3`) as a delimited token — `pr-2.3-x`
   matches row 2.3, `12.3` does not;
3. a title match — the row's text and the PR title name the same change, and exactly
   one PR pairs with exactly one row; anything softer is ambiguity.

The work list is every row whose PR is `MERGED` but isn't booked yet. Any ambiguity —
a merged PR whose branch or title carries a row id but matches no row, one that
matches two rows, two PRs matching one row — goes to the report, never a guess.
**Empty work list → the issue lane skips Phase 3** and runs Phase 5 alone; both lanes
still dispatch, as truth checks (they no-op when already true).

## Dispatch — the two lanes

**The issue and the artifact are booked in parallel by two `general-purpose`
subagents, launched in one message** (never `Explore` — both lanes write; never a
coder). Neither inherits this conversation, so give each its phases of this skill
**quoted verbatim**, plus the facts it needs:

| Lane | Phases | Also gets |
|---|---|---|
| issue | 3, then 5 | `owner/repo`, the issue number, the scratch dir, the work list (row id · `#NN` · title), and the full booked-row set Phase 5 sweeps |
| artifact | 4, plus Phase 3's diff-gate paragraph it refers back to | the artifact URL, the scratch dir, the work list, and the plan's landed/total counts for the recount |

**Neither lane touches the other's record**, so they never race the plan issue's
body: the artifact lane never runs `gh issue edit` — the marker pin is the join's —
and the issue lane never publishes a page. They share the scratch dir but not
filenames. Each returns one compact block for the Report:

- **issue** — rows booked (`id → #NN`, link repairs included), headings ticked,
  cross-ref issues ticked, whatever went unmatched or ambiguous, and any abort with
  its reason.
- **artifact** — `updated (x/y landed)` | `already true` | `skipped: <reason>`, and
  the URL its republish returned.

A lane that dies or returns nothing → its leg is skipped in the report, with the
reason; never re-run or take over the other lane.

## Phase 3 — Tick the issue rows *(issue lane)*

Flip only the matched rows, mirroring how the issue's already-booked rows look. No
booked row to mirror yet → tick the row's status cell in its own shape — the status
word (`Merged #NN`), a ✅ beside the id, or a checked box — always with the linked
`#NN`; several shapes fit → the one the table's own columns imply (a Status column
wins). A slice or section heading gains `— ✅ **DONE**` only when every row under it —
non-PR rows like validation steps included — is ticked **and** sibling headings
already use that convention.

Build `$SCRATCH/new-body.md` from `old-body.md` with the Write tool (cells carry
backticks and `$` a heredoc would interpolate; end the file with exactly one
newline), then inspect before anything is published:

```bash
SCRATCH=<the session scratch directory>
[ -s "$SCRATCH/old-body.md" ] && [ -s "$SCRATCH/new-body.md" ] || { echo "abort: empty body file" >&2; exit 1; }
diff "$SCRATCH/old-body.md" "$SCRATCH/new-body.md"
```

**The diff is the gate.** Legal hunks: a row line differing only inside its status
cell — the rest byte-identical, **and the line carries the id and matched `#NN` of a
work-list row**, so a tick that landed on the wrong row surfaces here — or a whole
`— ✅ **DONE**` heading line. Anything else, fix `new-body.md` and re-inspect; no
clean diff, no publish. Then a body that moved underneath you aborts instead of
clobbering the human's edit:

```bash
ISSUE=<the issue number>; SCRATCH=<the session scratch directory>
gh issue view "$ISSUE" --json body -q .body | sed -e 's/\r$//' | diff - "$SCRATCH/old-body.md" \
  || { echo "abort: issue changed mid-run — end the run, rerun /shipped" >&2; exit 1; }
gh issue edit "$ISSUE" --body-file "$SCRATCH/new-body.md" \
  && rm -f "$SCRATCH/old-body.md" "$SCRATCH/new-body.md" \
  && echo "issue #$ISSUE updated"
```

## Phase 4 — Tick the artifact *(artifact lane)*

Fetch the live page (WebFetch on the artifact URL) and save the returned source as
`$SCRATCH/old-page.html`. **Check it is the page's real source first**: it must carry
the HTML the page is built from — the chip/card classes you are about to flip. A
markdown rendering has none of them → skip and report; **never rebuild the page from
memory or a template**. Then copy to `$SCRATCH/new-page.html` and make the smallest
edits that make the page true to the ticks — keep its classes, structure, and design:

- the merged PR's chip/card → the page's own done state, plus the PR link where its
  cards carry links
- rows whose blockers are now all done — per the page's own dependency markup — lose
  their blocked state (→ the page's ready/next state)
- header stats and counters ("12 / 20 landed") → recount

The same gate as Phase 3 — `diff "$SCRATCH/old-page.html" "$SCRATCH/new-page.html"`:
every hunk must be a counter recount or a chip/card change carrying a work-list row's
id or `#NN` — an unblock flip names the chip whose blockers the work list just
satisfied — so a flip on the wrong card surfaces here; anything else, fix and
re-inspect. A clean diff → republish with the Artifact tool, **passing the page's URL
as the `url` parameter** — without it a republish mints a new page and orphans every
link to the old one. Keep the title and favicon the page already has. An empty diff →
don't republish; a refused republish → skip and report; a republish returning a
**different** URL failed: report both URLs and leave any marker untouched — never pin
the new page. Return the outcome and that URL; the marker pin is the join's.

## Phase 5 — Tick cross-referenced issues *(issue lane)*

Sweep the cross-references of **all** booked rows — not just the rows this run
flipped. The set: issues linked from those rows' cells or their merged PRs' bodies
(hand-off issues, module trackers — the plan issue itself excluded). Search each for a
row or checkbox naming the merged PR or its row id, and tick it in **that issue's**
own conventions through the same guarded write — freshness re-fetch and legal-hunk
inspection included — with per-issue copies (`$SCRATCH/old-<issue>.md` /
`$SCRATCH/new-<issue>.md`) and `-R <owner>/<repo>` when the issue lives in another
repo. A bare `#NN` there names **that** repo's PR, so match by row id or full URL
only. Only the cell that names the work — never any other line — and the same
ambiguity rule: unsure the cell means this work → the report, not a tick.

## Join — pin the artifact marker

**Once both lanes have returned**, pin the marker — but only when a title-matched
artifact (Phase 1's step 2) came back true (republished, or its diff was already
empty): put `<!-- shipped:artifact url=... -->` directly **above** the
`## PR breakdown` heading (that skill's redraw rewrites its section but preserves
everything before the heading; no such heading → append as the new last line),
**replacing** every existing `shipped:artifact` line. Re-fetch a fresh baseline — the
issue lane may have changed the body — and repeat the Phase 3 recipe; the new marker
line and the old ones' removal are the only legal hunks. Never write
`pr-breakdown:map` — that marker belongs to `/pr-breakdown`, and pointing its template
redraw at a hand-crafted page would clobber the page.

## Report

```
Shipped: <count> PRs booked — issue #N (<row ids>), artifact <updated (x/y landed) | already true | skipped>, <count> cross-refs
Unmatched: <#NN — no confident row / matches two rows> · <row n.k — recorded PR not found> (or none)
Skipped: <foreign-repo rows, a lane that skipped or died with its reason, headless> (or none)
```

`<count>` = rows newly booked, link repairs included. Add the marker URL if newly
pinned. A PR listing that filled its `-L 1000` cap left branch/title matching
incomplete — say so.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Writing evidence prose into a cell | Ticks and links only — the PR flow owns the story |
| Trusting cell position in a hand-evolved table | Escaped pipes (`\|`) shift cell counts — re-read the row before trusting the diff |
| A tick-shaped hunk on the wrong row | Fix `new-body.md` before publishing — publish-then-correct is never the remedy |
| A republish that returns a new URL | That leg failed: report both URLs, leave the marker alone |
| A lane writing the other's record | The artifact lane never edits an issue, the issue lane never publishes — the marker pin waits for the join |
| Running the lanes one after the other | Both go out in **one** message; only the marker pin needs both back |
