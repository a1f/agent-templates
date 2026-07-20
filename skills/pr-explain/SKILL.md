---
name: pr-explain
description: Use when the user invokes /pr-explain or wants a reader-facing explainer page for a pull request — writes a 2-3 minute, word-budgeted story of the change (bottom line, system delta map, author-order story, proof, limits), publishes it as a private claude.ai artifact, and maintains a marker-delimited teaser in the PR body.
argument-hint: "[#N | PR URL | blank = current branch's PR] [--refresh]"
---

# PR Explain

Turn one pull request into a page its owner actually reads: the change explained the
way a teammate would explain it at a whiteboard, in 2-3 minutes, with a picture of how
the system changed and the evidence it works. The audience is the repo's owner keeping
a mental model of a codebase agents typed — not a merge gatekeeper hunting defects.

## Arguments

| Form | Meaning |
|------|---------|
| *(blank)* | The open PR for the current branch (`gh pr view`) |
| `#N` or `N` | PR number in the current repo |
| a PR URL | That PR |
| `--refresh` | Rebuild the page and update the existing artifact + teaser in place |

## Runtime resolution

- **Template**: `~/.claude/at/templates/pr-explain-page.html` — the page skeleton
  (design tokens, chapter blocks, delta-map classes, minimap, legend). Staged by the
  installer with this skill's package extras. If it is missing (skill installed without
  its package), still ship: build a single-file HTML page with inline CSS following the
  chapter contract below — visual polish degrades, the contract does not.
- **Page file**: write the filled page to the session scratch directory (never into the
  target repo), named `pr-<owner>-<repo>-<number>.html`. A stable name means republishing
  in the same conversation keeps the same artifact URL.
- **Target repo**: the git repo of the working directory. Run every `gh` and `git`
  command there.

## The page contract — six chapters, hard budgets

| Chapter | Job | Budget |
|---------|-----|--------|
| Bottom line | What changed, why, impact, risk — the reader can stop here | 40-60 words |
| The map | How the system changed: one delta-encoded component map + minimap | ≤ 40 words + map |
| The problem | The concrete failing behavior — real command, error, or number first | 80-120 words + 1 block |
| The story | One paragraph per design decision, author order, key diffs annotated | 150-200 words + ≤ 2 blocks |
| The proof | Witnesses, gate numbers, runtime evidence — real, never invented | 40-70 words + evidence |
| The limits | What deliberately didn't change, non-goals, sharp edges | 40-60 words |

- Total prose 410-550 words; everything essential inside the first 200.
- Code/output blocks are excluded from the budget and capped at 10 lines each.
- Budgets are ceilings, not targets. Empty chapters are dropped, never padded.
- **Scaling**: a non-structural PR (docs, config, formatting, version bumps) gets no map
  and may shrink to five strong sentences across Bottom line / The story / The limits.
  A structural PR gets the full page. Conditional diagrams are a quality signal — a
  forced diagram teaches the reader to stop looking at diagrams.

## Phase 1 — Gather

```bash
gh pr view <N> --json number,title,body,url,state,baseRefName,headRefName,closingIssuesReferences
gh pr diff <N>
gh pr view <N> --json commits --jq '.commits[].messageHeadline'
gh pr checks <N> || true
```

- **The why**: read the linked issue (`closingIssuesReferences`) or the issue/PRD the
  body references. The problem chapter comes from there, not from the diff.
- **Evidence**: if `<target_repo>/.v1-runs/evidence/` exists for this PR's branch, read
  it (RED/GREEN witnesses, gate transcript, runtime artifacts). Without it, the proof
  chapter degrades to `gh pr checks` results and the tests visible in the diff. Never
  fail for lack of evidence; never invent it either.

## Phase 2 — Understand (before writing a word)

1. **Name the one big thing** — the single decision that drives the diff. If you cannot
   name it in one sentence, re-read the diff; do not start writing.
2. **Group hunks into author-order cohorts** — data/schema first, then logic, then call
   sites, then tests. The story follows this order, never file order.
3. **Pick the key moments** — at most 3 hunks that carry the decision. Everything else
   is summarized in prose.
4. **Derive the delta map** (structural PRs only):
   - Nodes are the changed components at the granularity a component diagram would show
     (a module/file, not a function). Classify each from the diff: added, modified,
     removed. Removed components stay on the map.
   - Add unchanged 1-hop neighbors (importers/importees of changed files), dimmed —
     they are the blast radius. Dim, never hide.
   - Cap ~20 elements: collapse unchanged neighbors into their parent folder as one
     dimmed node when over.
5. **Build the minimap**: the repo's top-level directories, alphabetical, equal-width
   cells, with the directories containing changes marked. Same strip, same order, every
   PR — recognition over re-parsing.

## Phase 3 — Write the chapters

Draft the prose in a scratch buffer before touching HTML, then verify mechanically:

- `wc -w` each chapter; cut until inside its budget.
- Grep the draft for every banned word below; rewrite any hit.
- Read each sentence once more: does it point at a hunk, a number, or an output the
  page shows? A sentence that cannot cite its evidence gets cut.

### Style contract

1. **Bottom line first.** Change, reason, impact in the first three sentences.
2. **One PR, one big thing.** Secondary changes get one line each, never their own arc.
3. **Every claim points at evidence** — a diff hunk, a gate line, a check result, a
   screenshot. "Faster", "safer", "fixed" each come with a number or output.
4. **Concrete before abstract.** The failing command, error, or diff appears before any
   general statement about it. Examples are trimmed from the real diff, never invented.
5. **Data over adjectives; 25-word sentences; one idea per sentence.** "41 lines in the
   parser", never "a clean, minimal change".
6. **One name per concept — the name from the code.** Present tense for new behavior,
   past tense only for the behavior it replaced.
7. **Say what didn't change.** The limits chapter is what makes the brevity trustworthy.
8. **No section exists to be complete — only to be read.**

Banned on sight: leverages, robust, seamless, comprehensive, delve, streamlined,
powerful, simply, ensures, significantly, various, clearly, essentially, "it's worth
noting", and "should" when describing behavior (the page either shows it verified or
drops the claim).

## Phase 4 — Build the page

- Start from the template; keep its tokens and classes; fill the `SLOT` comments.
- Everything inline (CSS in the file, no external requests); light and dark themes come
  from the template's token overrides — do not strip them.
- **Delta map encoding** (must match the template legend):
  - added = green node + `+` badge · modified = amber node + `~` badge · removed = red
    node + `−` badge, kept on the map · unchanged neighbors dimmed.
  - New edges solid green; removed edges thin red; unchanged edges translucent grey.
  - Never color without the glyph badge — the badges are the colorblind-safe channel.
- Diff blocks use the template's `del`/`add`/`ctx` classes; ≤ 10 lines per block.

## Phase 5 — Publish

- Publish the page file with the Artifact tool: title `PR #<N> — <imperative title>`,
  favicon `📖` (keep it stable across refreshes), a one-sentence description.
- `--refresh` in the same conversation: republish the same file path — same URL. From a
  later session: read the existing artifact URL out of the teaser block and pass it as
  the Artifact `url` parameter so the page updates in place.
- If the Artifact tool is unavailable (headless/CI run), fall back: put the full story,
  as markdown, into the PR-body block below instead of a teaser, and say so in your
  report. Never fail the run because publishing is unavailable.

## Phase 6 — The teaser in the PR body

Maintain exactly one marker-delimited block in the PR description:

```markdown
<!-- pr-explain:begin -->
### The story of this PR
<the bottom-line chapter, verbatim — three sentences>

**[Read the explainer](<artifact-url>)**<map tail — only when the page has a map>
<!-- pr-explain:end -->
```

- Read the current body (`gh pr view --json body`), remove any existing block between
  the markers, append the fresh block, write back with `gh pr edit --body-file`. If that fails on a GraphQL projectCards deprecation error (a gh CLI quirk on repos with classic projects), write the same body with `gh api repos/<owner>/<repo>/pulls/<N> -X PATCH -F body=@<file>` instead.
- The map tail (` · map: <n> changed components, <m> untouched neighbors`) is emitted only when the page includes the map chapter; a non-structural PR's teaser ends at the link.
- Never touch prose outside the markers. If the body is empty, the block is the body.

## Report

End with: the artifact URL, total prose word count, chapters emitted vs dropped, map
included or skipped (with the reason), and the PR whose teaser was updated.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Padding a thin PR to fill budgets | Budgets are ceilings; five strong sentences beat 500 padded words |
| A map for a non-structural change | Skip it — conditional diagrams are the quality signal |
| Raw diff dumps | ≤ 3 annotated moments, ≤ 10 lines each, chosen for the decision they carry |
| Inventing proof | No evidence dir → CI checks only; never fabricate witnesses or numbers |
| A new artifact URL on refresh | Same file path in-session; pass `url` across sessions |
| Editing outside the teaser markers | Only the block between the pr-explain markers is yours |
| Writing the page before the map | Phase 2 comes first — the map decides what the story must explain |
