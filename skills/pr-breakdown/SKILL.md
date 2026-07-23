---
name: pr-breakdown
description: Use when a PRD issue's slice plan needs breaking into small ~100-200 LOC pull requests recorded as a table in that issue and drawn as a published PR-map artifact, or invokes /pr-breakdown.
---

# PR Breakdown

Break the slice plan in a PRD issue into **small PRs (~100–200 LOC, excluding
tests)** and keep two synced views of them:

- a **table** in the **same issue** — one row per PR, carrying its dependency, status, and size;
- a **PR map** — a published claude.ai artifact drawing the PRs as waves with
  blocked-by edges and a detail card each, like the one the issue links to.

**The issue table is the single source of truth; the map is a projection of it.**
Every run regenerates the map from the table, so the two never drift.

```
/pr-breakdown [--issue=N]

  1. Find the issue, slice plan, and any existing map + statuses
  2. Split each slice into PR rows (blocked-by + status)
  3. Show it, wait for approval          (gate)
  4. Fill the map template from the rows
  5. Publish / update the artifact
  6. Write table + map link to the SAME issue
```

## Phase 1 — Find the issue, plan, and existing state

Use `--issue=N` if given. Otherwise scan the conversation for the last
`PRD published: ... (issue #N)` line; if there's none, ask. If you auto-detected
it, confirm the number with the user. Read the body.

- No `## Build plan` section → **stop** and tell the user to run `/to-issues` first;
  don't invent a breakdown.
- Build plan says `No slicing — single PR` → emit one `### Slice 1 — <name> (1 PR)`
  row (derive `<name>` from the PRD's *What we're building*) and continue.

Then capture what a re-run must preserve, from any existing `## PR breakdown`:

- The **map URL** in `<!-- pr-breakdown:map url=<url> -->`. Reuse it in Phase 5 so
  the same artifact updates instead of a new one appearing.
- The **Status** cell of every existing row, keyed by its `n.k` id. Carry these
  forward — a re-run never resets a `Merged`/`In review` row back to `Todo`.

## Rules for splitting

- 100–200 LOC per PR, excluding tests. Over ~200 → split further; a tiny slice may be one PR.
- One cohesive, reviewable, demoable change per PR.
- Foundations first: reusable primitives before the PRs that wire them up.
- **Rows only.** Do NOT write coder prompts (module boundary, acceptance criteria,
  etc.) — those are generated later, one PR at a time.

## Phase 2 — Draft the rows

Derive each `<name>` from the slice's *What*. One table per slice:

```markdown
## PR breakdown

<!-- pr-breakdown:map url=<artifact-url, or omit the marker on the first run> -->
🗺️ **[PR map](<artifact-url>)** — waves, blocked-by edges, and a card per PR. Regenerated from the table below.

### Slice 1 — <name> (2 PRs)
| PR | What | LOC | Blocked by | Status | Done when |
|----|------|-----|-----------|--------|-----------|
| 1.1 | ... | ~120 | — | Todo | <observable result> |
| 1.2 | ... | ~140 | 1.1 | Todo | ... |

**Estimated total: ~N PRs · N waves.**
```

- **Blocked by** — a space/comma-separated list of the `n.k` ids this PR needs
  merged first, across *any* slice, or `—` for none. This is the only dependency
  record; parallelism and waves are derived from it, so drop the old `∥` note.
- **Status** — one of `Todo` · `In review #NN` · `Merged #NN`. New rows are `Todo`;
  preserved rows keep the Phase 1 value. If a row carries a `#NN`, you may refresh it
  from live state (`gh pr view NN --json state,merged`) — merged → `Merged #NN`, open
  → `In review #NN`. Discovering *unrecorded* PRs is `/course-correct`'s job, not this
  skill's.
- **Gate PRs** — a PR whose job is validation machinery that blocks merging (a CI
  gate, an image/deploy/e2e gate). Name it as such in *What* ("Delivery gate"); it
  gets the `gate` styling in the map. No extra column.

**Waves** are the topological layering of *Blocked by*, spanning all slices:
`wave(pr) = 0` if it has no deps, else `1 + max(wave of its deps)`. Same-wave PRs
share no blocking relationship — they are the map's columns and can be built at once.

## Phase 3 — Approve (gate)

Show the full breakdown in chat — the per-slice tables plus the derived wave list
(which PRs land together). **Wait for approval or edits** before touching the issue
or publishing anything.

## Phase 4 — Fill the map template

- **Template**: `~/.claude/at/templates/pr-breakdown-map.html` — design tokens plus
  the `lane` / `chip` / `card` / edge classes and the `data-id` / `data-deps`
  contract. Missing (or stale — prefer the repo's `templates/pr-breakdown-map.html`
  when running inside this repo)? Still ship: build a single-file HTML page with
  inline CSS on the same contract — chips carry `data-id`/`data-deps` and an inline
  script draws the edges from them.
- Write the filled page to the session scratch directory (never the target repo) as
  `pr-map-<owner>-<repo>-<issue>.html`, owner/repo from `gh repo view`.

Fill every `SLOT`, keeping the tokens and class names:

- **Header** — `owner/repo · issue #N`, a title (`<goal>, one small PR at a time`), a
  one-paragraph summary, and 4–6 `.stat` blocks (PRs merged `x / y`, PRs planned,
  ~LOC per PR, waves, moments that need the human).
- **Lanes** — one `.lane` per wave, left to right; set
  `grid-template-columns: repeat(<wave count>, 1fr)`. Each PR is a `.chip` with
  `id="m-<slug>"`, `data-id="<slug>"`, `data-deps="<slug> <slug>"`, and `href="#<slug>"`,
  where `<slug>` is the `n.k` id made anchor-safe (`.` → `-`, so `1.2` → `1-2`). Add
  the status/gate class (`gate`, `done` for Merged, `active` for In review) and a
  `<span class="adot"></span>` when a PR needs the human once. Never author edge SVG —
  the script draws it from `data-deps`.
- **Cards** — one `.wave` section per wave with a `.card` per PR (`id="<slug>"`):
  keycap `PR n.k`, title, `after:` links to its blockers, the *What* as a sentence or
  two, an optional `why`, a `Done when` list, and — only on merged PRs — an `.ev`
  evidence line linking the PR. `gatecard` for gates, `donecard` for merged.

## Phase 5 — Publish / update the artifact

Use the Artifact tool: title `<repo> — PR map`, favicon `🗺️` (stable across reruns),
a one-sentence description.

- Reran in the same conversation → republish the same file path (keeps the URL).
- Reran in a later session → pass the Phase 1 map URL as the `url` parameter so the
  same artifact updates. If that fails (artifact deleted or not owned), publish
  without `url` and let Phase 6 record the new link.
- Artifact tool unavailable (headless/CI) → skip publishing; Phase 6 writes the table
  with the existing URL (or none) and the report says the map wasn't refreshed.

Capture the returned URL for the marker and the visible link.

## Phase 6 — Write to the same issue

Keep canonical order PRD → `## Build plan` → `## PR breakdown`; `## PR breakdown` is
last and this skill owns it whole. Regenerate it — marker with the resolved URL, the
visible map link, then the per-slice tables — so a re-run replaces it in place. The
rebuild keys on the exact `## PR breakdown` heading; `tr -d '\r'` guards CRLF; abort on
an empty read:

```bash
ISSUE=<the issue number>; NEW=$(mktemp)
# ...write the new "## PR breakdown" section (marker + map link + tables) to "$NEW"...
CUR=$(gh issue view "$ISSUE" --json body -q .body | tr -d '\r')
[ -n "$CUR" ] || { echo "abort: empty issue body" >&2; exit 1; }
HEAD=$(printf '%s\n' "$CUR" | awk '/^## PR breakdown/{exit} {print}')
OUT=$(mktemp)
{ printf '%s\n\n' "$HEAD"; cat "$NEW"; } > "$OUT"
gh issue edit "$ISSUE" --body-file "$OUT"
rm -f "$NEW" "$OUT"
echo "PR breakdown appended to issue #$ISSUE"
```

## Report

End with `PR breakdown appended to issue #N`, then: the map artifact URL (or that it
wasn't refreshed and why), the PR / wave counts, and any statuses carried forward.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Editing the map by hand | The table is the source of truth; regenerate the map from it |
| A new artifact each run | Reuse the Phase 1 map URL (`url` param) in a later session |
| Resetting a merged row to Todo | Carry every existing Status cell forward by `n.k` id |
| Authoring edge SVG in the map | Emit `data-deps` on chips; the inline script draws edges |
| Coder prompts in the rows | Rows only — prompts come later, one PR at a time |
