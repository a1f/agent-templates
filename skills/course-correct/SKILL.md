---
name: course-correct
description: Use when PRs have landed mid-build and the plan needs re-checking against a PRD issue's goal and re-planning, or invokes /course-correct.
---

# Course Correct

Step back from a PRD issue mid-build and ask what per-PR review can't:
**does the merged work plus the remaining plan still reach the goal — and if not,
what to add, remove, or re-scope?**

**Judges the plan, not the code** — `reviewer` and `critic` own quality; this
never writes code or PRs, only edits the plan in place, behind a gate.
**Checkpoint-aware** — each run digests only what merged since the last; re-run it
each time a wave of PRs lands.

```
/course-correct [--issue=N] [--since=<git-ref>]

  1. Find the issue; read goal + plan + the checkpoint
  2. Gather what landed since the checkpoint (merged PRs + diffs)
  3. Read the merged diffs against the goal   (read-only subagents)
  4. Judge drift; draft a Status refresh + plan edits
  5. Discuss and approve                       (gate)
  6. Apply to the SAME issue; post an audit comment; advance the checkpoint
```

## Phase 1 — Find the issue and read the checkpoint

Use `--issue=N` if given; else scan the conversation for the last
`PRD published: ... (issue #N)` line, or ask. Confirm an auto-detected number.

The body must have `## Build plan` **and** `## PR breakdown` — if either is
missing, **stop** and run `/to-issues` then `/pr-breakdown` first.

Read, and keep separate:

- **The goal** — the PRD prose (*The problem* / *What we're building* / decisions
  / scope). Re-read it fresh each run — it's the yardstick; if the goal itself was
  rewritten, re-judge the whole plan against the new one.
- **The plan** — the `## Build plan` slices and `## PR breakdown` rows.
- **The checkpoint** — the marker left in the Status block:

  ```
  <!-- course-correct baseline=<sha> checked=<iso-date> -->
  ```

  `baseline` is the commit last reconciled. Resolve it into `BASELINE`, in order:
  1. `--since=<ref>`, if given.
  2. the marker's `baseline=<sha>`, if still in history (`git cat-file -e
     "<sha>^{commit}"` succeeds).
  3. otherwise — first run, missing marker, or a force-pushed sha — reconcile the
     whole build from the parent of its earliest merged PR:

     ```bash
     DEF=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
     OID=$(gh pr list --search "is:merged base:$DEF" --json mergeCommit,mergedAt \
       --jq 'map(select(.mergeCommit.oid)) | sort_by(.mergedAt)[0].mergeCommit.oid // empty')
     [ -n "$OID" ] || { echo "no merged PR — pass --since=<ref>" >&2; exit 1; }
     BASELINE=$(git rev-parse "$OID~1"); echo "BASELINE=$BASELINE"
     ```

## Phase 2 — Gather what landed since the checkpoint

**Find what merged since the baseline** — match by ancestry, never by comparing
abbreviated `git log` SHAs against gh's full OIDs. Shell vars don't carry between
steps, so re-pin `BASELINE` first:

```bash
BASELINE=<the ref/sha resolved in Phase 1>
git fetch -q origin
DEF=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)
BASE=$(git rev-parse "$BASELINE")
NEW=$(git rev-parse "origin/$DEF")          # reconcile point → next baseline
SINCE=$(git show -s --format=%cs "$BASE")   # bounds the search; the ancestry test below is the source of truth
HITS=$(gh pr list --search "is:merged base:$DEF merged:>=$SINCE" -L 200 \
  --json number,title,mergeCommit \
  --jq '.[] | select(.mergeCommit.oid) | "\(.mergeCommit.oid)\t#\(.number)\t\(.title)"' |
while IFS=$'\t' read -r OID NUM TITLE; do
  git merge-base --is-ancestor "$OID" "$NEW" \
    && ! git merge-base --is-ancestor "$OID" "$BASE" \
    && echo "$NUM — $TITLE"
done)
[ -n "$HITS" ] || { echo "nothing merged since last check"; exit 0; }
printf '%s\n' "$HITS"
echo "NEW=$NEW"      # next baseline — write this sha into the Phase 4 marker
```

Map each PR to a plan row (rows carry `#NN` links): `#NN — <title> — <slice/PR
row, or "unplanned">` — by the row's `#NN` link if it has one, else by matching
the PR title to the row's *What*. Flag any merged PR mapping to **no** row
(unplanned work) and any row whose PR merged but isn't recorded (bookkeeping
drift) — both feed the verdict.

## Phase 3 — Read the diffs against the goal

**Send each diff to a read-only subagent — judge it against the goal, never
re-review its code.** For each merged PR (or each subsystem, if PRs cluster),
launch the subagent via the Agent tool (`Explore` or `general-purpose`, never a
coder). Give it the PRD goal and the PR's diff (`gh pr diff <NN>`); have it return
a compact finding:

- **Advances the goal?** — toward *What we're building*, or sideways?
- **Scope drift** — built something unasked, or silently reversed a decision?
- **Deferred** — TODOs, stubs, narrowed behavior a *future* PR must now cover.
- **Plan impact** — does it make a planned PR unnecessary, insufficient, or newly
  blocked, or expose missing work?

Run them in parallel (one message, many calls); collect the findings.

## Phase 4 — Judge drift and draft the correction

**Turn the findings into a verdict and edits that touch only what drifted.**

**Verdict** — one of:
- **On track** — work advances the goal; the plan still closes it. Skip the edits,
  but still refresh Status and advance the checkpoint through Phases 5–6.
- **Drifting** — gaps remain, or the plan no longer closes them. Propose edits.

**Plan edits** — each an explicit op with a one-line reason, naming the row:
**ADD** / **REMOVE** / **RE-SCOPE** / **RE-ORDER** a slice (`#n` in Build plan —
*Demoable as / Mode / Size / Blocked by*) or a PR row (`n.k` in PR breakdown —
*What / LOC / Blocked by / Status / Done when*). Rows only, no coder prompts; PRs
stay at ~35 counted lines (added lines excluding tests, lockfiles, and generated
output) — the size gate refuses over 50 across 3+ files, over 100 across 1–2. Edits here change the table but not its PR-map
artifact — Phase 6 flags a re-run of `/pr-breakdown` to redraw it.

Always write the rebuilt **Status block** to `status.md` — even on track, since
Phase 6 advances the checkpoint from it. Keep it flat below its heading (`###` /
text only, no `## `), ending in the marker, then the `---` rule. The marker's
`baseline` is the `NEW` sha from Phase 2; both `<date>` tokens are today:

```markdown
## Status — updated <date>

<one line per slice — status · PRs done>

**Overall: <x> / <y> PRs merged.** Next: <slice / PR>.

<!-- course-correct baseline=<NEW sha> checked=<date> -->
---
```

## Phase 5 — Discuss and approve (gate)

**Surface the call before any write.** Present in chat: the **verdict** + a
one-line headline; the **findings** that drove it; the **plan edits**; a **Status
preview**. Wait for approval or edits — touch nothing until then. On track, no
edits — still confirm the Status refresh, then apply in Phase 6.

## Phase 6 — Apply to the same issue

**Post the drift record before you overwrite the body.** Write the verdict +
findings + the approved edits to `report.md` and comment it:

```bash
ISSUE=<the issue number>
gh issue comment "$ISSUE" --body-file report.md
```

Then rebuild the body in three steps — **seed → edit → assemble** — so a re-run
replaces each owned section without dropping the prose between them.

**Seed** the owned plan sections from the live body:

```bash
ISSUE=<the issue number>
gh issue view "$ISSUE" --json body -q .body | tr -d '\r' > body.txt
[ -s body.txt ]  || { echo "abort: empty issue body" >&2; exit 1; }
[ -s status.md ] || { echo "abort: status.md missing — write it in Phase 4" >&2; exit 1; }
awk '/^## Build plan/{f=1} f && /^## PR breakdown/{exit} f' body.txt > buildplan.md
awk '/^## PR breakdown/{f=1;print;next} f&&/^## /{exit} f'   body.txt > prbreakdown.md
```

**Edit** `buildplan.md` / `prbreakdown.md` — Read each file (the Edit tool
requires it), then apply the approved ADD/REMOVE/RE-SCOPE/RE-ORDER ops and nothing
else. The files start as exact copies, so this is where the correction actually
happens; skip it only on an on-track verdict.

**Assemble** and publish — command substitution strips trailing blanks, so one
blank line between parts keeps the result idempotent across runs:

```bash
ISSUE=<the issue number>
# PRD = everything before Build plan with any Status block stripped (anchored on its
# heading or the '---' status.md owns, so prose below survives re-runs); TAIL = after PR breakdown.
PRD=$(awk '
  /^## Build plan/{exit}
  /^## Status/{s=1;next}
  s&&/^## /{s=0}
  s&&/^---$/{s=0;next}
  s{next}
  !b&&!NF{next}
  {b=1;print}' body.txt)
TAIL=$(awk '/^## PR breakdown/{b=1;next} b&&/^## /{b=0;t=1} t' body.txt)
STATUS=$(cat status.md); BUILD=$(cat buildplan.md); PRBD=$(cat prbreakdown.md)
OUT=$(mktemp)
{ printf '%s\n' "$STATUS"
  [ -n "$PRD" ]  && printf '\n%s\n' "$PRD"
  printf '\n%s\n' "$BUILD"
  printf '\n%s\n' "$PRBD"
  [ -n "$TAIL" ] && printf '\n%s\n' "$TAIL"
} > "$OUT"
gh issue edit "$ISSUE" --body-file "$OUT" \
  && rm -f "$OUT" body.txt status.md buildplan.md prbreakdown.md report.md \
  && echo "Course-correction applied to #$ISSUE"
```

If any **PR breakdown** row changed (added, removed, re-scoped, or re-ordered), tell
the user its PR-map artifact is now stale and to re-run `/pr-breakdown` to redraw it —
that skill regenerates the map from the table it just edited.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Re-reviewing code quality | Judge plan-vs-goal only; quality is reviewer/critic's job |
| Editing the issue before the gate | Nothing is written until Phase 5 approval |
| Re-digesting already-reconciled PRs | Start from the checkpoint baseline, not the issue's first commit |
| Comparing gh's full OIDs to abbreviated `git log` SHAs | Test ancestry with `git merge-base --is-ancestor` |
