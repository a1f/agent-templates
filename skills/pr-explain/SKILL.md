---
name: pr-explain
description: Use when the user invokes /pr-explain or wants a reader-facing explainer page for a pull request — writes a 2-3 minute, word-budgeted story of the change with a system delta map and proof, publishes it as a private claude.ai artifact, and maintains a marker-delimited teaser in the PR body.
argument-hint: "[#N | PR URL | blank = current branch's PR]"
---

# PR Explain

Write the page a teammate would draw at a whiteboard. The audience is the repo's owner
keeping a mental model of a codebase agents typed — not a merge gatekeeper hunting
defects.

## Arguments

| Form | Meaning |
|------|---------|
| *(blank)* | The open PR for the current branch |
| `#N` or `N` | PR number in the target repo |
| a PR URL | That PR |

## Runtime resolution

- **Template**: `~/.claude/at/templates/pr-explain-page.html` (design tokens + chapter,
  delta-map, and minimap classes). If it is missing, still ship: build a single-file HTML
  page with inline CSS following the chapter contract — visual polish degrades, the
  contract does not.
- **Page file**: write the filled page to the session scratch directory (never the
  target repo) as `pr-<owner>-<repo>-<number>.html`, owner/repo parsed from the PR's `url`.
- **Target repo**: the git repo of the working directory; run every `gh`/`git` command there.

## The page contract — six chapters, hard budgets

| Chapter | Job | Budget |
|---------|-----|--------|
| Bottom line | What changed, why, impact, risk, in the first three sentences — the reader can stop here | 40-60 words |
| The map | How the system changed: one delta map + minimap | ≤ 40 words + map |
| The problem | The concrete failing behavior — real command, error, or number first | 80-120 words + ≤ 1 block |
| The story | One paragraph per design decision, author order, key diffs annotated | 150-200 words + ≤ 2 blocks |
| The proof | Witnesses, gate numbers, runtime evidence | 40-70 words + evidence |
| The limits | What deliberately didn't change, non-goals, sharp edges | 40-60 words |

- Total prose ≤ 550 words; everything essential inside the first 200. Budgets are
  ceilings, not targets — empty chapters are dropped, never padded.
- Code/output blocks are excluded from the budget and capped at 10 lines each.
- **Scaling**: a non-structural PR (docs, config, formatting, version bumps) gets no map
  and may shrink to five sentences across Bottom line / The story / The limits. A
  structural PR gets the full page.

## Phase 1 — Gather

```bash
branch="$(git branch --show-current)"           # blank arg; empty output → detached HEAD: stop, ask for #N
gh pr list --head "$branch" --json number,url   # [] → no open PR: stop, ask for #N
gh pr view <N> --json number,title,body,url,headRefName,additions,deletions,createdAt
gh pr diff <N>
gh pr checks <N> || true
```

- **The why**: read the issue/PRD the PR body references (`Closes #N` / `Refs #N`;
  prefer `Closes`, first match) via
  `gh issue view <N> --json title,body`. The problem chapter comes from there — the
  slice/PR row the body names, else the issue's headline problem — not from the diff.
  None referenced → derive it from the PR body and diff, and say so.
- **Evidence**: with the head branch slugged `/`→`_`, read
  `<target_repo>/.v1-runs/evidence/<slug>/evidence.json` — the make-pr/-lite handoff:
  `behaviors[]` with RED and GREEN witnesses, `gates[]` with the run's real gate numbers,
  `runtime` artifact paths relative to that dir. The proof chapter quotes it verbatim:
  the RED tag carries `red.key_output` (the witnessed failure reason), the GREEN tag
  what made it pass plus `+<lines_added>` lines, one gate chip per `gates[]` row from
  its `key_output`. Never invent evidence: without that file, the proof chapter degrades
  to `gh pr checks` plus the tests visible in the diff. Checks empty too → cite the
  diff's test files. Gate numbers claimed in the PR body appear only attributed
  ("PR body reports: pytest 18 passed"), never as verified chips.

## Phase 2 — Understand (before writing a word)

1. **Name the one big thing** — the single decision that drives the diff, in one sentence.
2. **Group hunks into author-order cohorts** — data/schema, then logic, then call sites,
   then tests. The story follows this order, never file order.
3. **Pick the key moments** — at most 3 hunks that carry the decision; the rest is
   summarized in prose.
4. **Derive the delta map** (structural PRs only): the diff's changed components, each
   classified added / modified / removed. Components are modules/files, not functions;
   config, lockfiles, and fixtures are not components. Removed components stay on the
   map. Add unchanged 1-hop neighbors (importers/importees), dimmed, never hidden. Cap
   ~20 components; collapse unchanged neighbors into their parent folder when over.
5. **Build the minimap**: git-tracked top-level directories
   (`git ls-tree -d --name-only HEAD`), byte-sorted, equal-width cells; mark the ones
   containing changes.

## Phase 3 — Write

Draft the prose in a scratch buffer under this contract:

1. **One PR, one big thing.** Secondary changes get one line each, never their own arc.
2. **Every claim points at evidence the page shows** — a hunk, a gate line, a check
   result, a screenshot. "Faster", "safer", "fixed" each come with a number or output.
3. **Concrete before abstract.** The failing command, error, or diff appears before any
   general statement about it; examples are trimmed from the real diff.
4. **Data over adjectives; ≤ 25-word sentences; one idea per sentence.**
5. **One name per concept — the name from the code.** Present tense for new behavior,
   past tense only for what it replaced.

Banned on sight: leverages, robust, seamless, comprehensive, delve, streamlined,
powerful, simply, ensures, significantly, various, clearly, essentially, "it's worth
noting", and "should" when describing behavior.

Then verify mechanically: `wc -w` each chapter and cut to budget; grep the draft for
every banned word and rewrite hits.

## Phase 4 — Build

- Fill the template's `SLOT` comments; keep its tokens, classes, and all four theme
  token blocks; delete the whole `.chapter` div of any dropped chapter. Everything stays inline —
  the artifact CSP blocks external requests.
- **Delta map**: use the classes the template's SLOT comments name; never color a node
  without its `+`/`~`/`−` glyph badge — the colorblind-safe channel. Grow the SVG
  viewBox height if the layout needs it.
- Screenshots embed as `data:` URIs via `img.evidence`.

## Phase 5 — Publish

- Artifact tool: title `PR #<N> — <imperative title, ≤ 8 words>`, favicon `📖` (stable
  across reruns), a one-sentence description.
- Rerun in the same conversation → republish the same file path (same URL). Rerun in a
  later session → pass the teaser's artifact URL (from the Phase 1 body) as the `url`
  parameter. Publishing with `url` fails (artifact deleted or not owned) → publish
  without it; Phase 6 rewrites the teaser with the new link.

## Phase 6 — The teaser

Maintain exactly one marker-delimited block in the PR description:

```markdown
<!-- pr-explain:begin -->
### The story of this PR
<the Bottom line chapter, verbatim>

**[Read the explainer](<artifact-url>)**<map tail>
<!-- pr-explain:end -->
```

- Map tail (only when the page has a map): ` · map: <n> changed components, <m> unchanged
  neighbors` — singular when a count is 1; drop the neighbors clause when it is 0.
- Re-read the body with `gh pr view <N> --json body` — it may have changed since
  Phase 1; replace the block between the markers in place (append if absent); write
  back with `gh pr edit <N> --body-file <file>`.
- If that fails on a GraphQL projectCards deprecation error (a gh quirk on repos with
  classic projects), write the same body with
  `gh api repos/<owner>/<repo>/pulls/<N> -X PATCH -F body=@<file>`.
- Artifact tool unavailable (headless/CI): the full chapters, as markdown, go between
  the markers in place of the teaser. Say so in your report.
- Never touch prose outside the markers. Empty body → the block is the body.

## Report

End with: the artifact URL, total prose word count, chapters emitted vs dropped, map
included or skipped (with the reason), and the PR whose teaser was updated.
