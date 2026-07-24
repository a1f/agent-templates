---
name: pr-explain
description: Use when the user invokes /pr-explain or wants a reader-facing explainer page for a pull request — a short, plain-words page with five chapters (what it is for, a map of the touched files, the tests, the proof, and commands to try it), published as a private claude.ai artifact with a teaser in the PR body.
argument-hint: "[#N | PR URL | blank = current branch's PR]"
---

# PR Explain

Write the page you would draw at a whiteboard for the person who owns this repo. They
want to keep a clear mental model of code that agents typed. They are not hunting for
bugs — a reviewer does that. They want to *understand the change fast*.

Two rules run through the whole page:

- **Plain words.** Say it the way you would to a smart friend who has not seen the code.
  If a code word is the only word that fits (`hash`, `symlink`, `CI`), say what it does in
  plain words right after — once. Short sentences, one idea each. Active voice. Talk to the
  reader: "you", "your". Start with the point; no wind-up.
- **Sharp, not padded.** Every chapter is a few clean statements, not a wall and not a
  bullet list. Cut any sentence that does not earn its place.

## Arguments

| Form | Meaning |
|------|---------|
| *(blank)* | The open PR for the current branch |
| `#N` or `N` | PR number in the target repo |
| a PR URL | That PR |

## Runtime resolution

- **Template**: `~/.claude/at/templates/pr-explain-page.html` — design tokens plus the
  `.bottomline`, `.tree`, `.wit`, `.gate-chip`, and `.cmd` classes the chapters use. Missing?
  Still ship: build a single-file HTML page with inline CSS that follows the chapter
  contract. Visual polish degrades; the contract does not.
- **Vale config**: `~/.claude/at/templates/pr-explain.vale.ini`, staged with the template. It
  names the write-good / proselint / Google packages the mechanical prose gate runs. Missing,
  or `vale` not installed → the gate degrades to the `wc` + banned-word checks.
- **Page file**: write the filled page to the session scratch directory (never the target
  repo) as `pr-<owner>-<repo>-<number>.html`, owner/repo parsed from the PR's `url`.
- **Target repo**: the git repo of the working directory; run every `gh`/`git` command there.

## The page — five chapters

Each chapter answers one question. Keep to the budget; a budget is a ceiling, not a target.
Drop an empty chapter, never pad it.

| # | Chapter | The question it answers | Budget |
|---|---------|-------------------------|--------|
| 1 | What this is for | Why did we build this, what is it, and what changes once it merges? | 60-100 words |
| 2 | The map | Which files did we touch, and what did we do in each? | tree + ≤ 40 words + ≤ 2 diffs |
| 3 | The tests | What do the tests set up and check, and how did they go RED then GREEN? | 50-90 words |
| 4 | The proof | What did we run to show it really works? | 40-70 words + evidence |
| 5 | See for yourself | What can you paste to confirm it yourself? | ≤ 40 words + commands |

Total prose ≤ 380 words. Code, diffs, the tree, and command blocks do not count, and each
diff or command block caps at 10 lines. A tiny PR (docs, a version bump, one-line config)
shrinks to Chapter 1, a one-line tree, and Chapter 5 — no forced tests or proof.

## Phase 1 — Gather

```bash
branch="$(git branch --show-current)"           # blank arg; empty output → detached HEAD: stop, ask for #N
gh pr list --head "$branch" --json number,url    # [] → no open PR: stop, ask for #N
gh pr view <N> --json number,title,body,url,headRefName,additions,deletions,createdAt,files
gh pr diff <N>
gh pr checks <N> || true
```

Always pass the explicit `<N>` — a bare `gh pr view` targets the current branch's PR, which
may not be the one you were asked about. `--json files` gives every touched path with its
`additions`/`deletions`; that list builds the Chapter 2 tree.

- **The why (Chapter 1)**: read the issue or PRD the PR body references (`Closes #N` /
  `Refs #N`; prefer `Closes`, first match) with `gh issue view <N> --json title,body` (this
  repo needs `--json`, a bare `gh issue view` errors on classic project cards). The reason
  comes from there — the slice/PR row the body names, else the issue's headline problem — not
  from the diff. Nothing referenced → derive it from the PR body and diff, and say so on the
  page.
- **Evidence (Chapters 3-4)**: slug the head branch (`/` and whitespace → `_`) and read
  `<target_repo>/.v1-runs/evidence/<slug>/evidence.json` — the make-pr / make-pr-lite handoff.
  It carries `behaviors[]` (each with a RED and a GREEN witness), `gates[]` (real gate numbers
  from the run), and `runtime` (artifact paths relative to that dir). Chapters 3 and 4 quote it
  verbatim: the RED witness carries the failure reason, the GREEN witness what made it pass plus
  `+<lines_added>`, one gate chip per `gates[]` row. **Never invent evidence.** No file → the
  proof degrades to `gh pr checks` plus the test files in the diff. Checks empty too → cite the
  diff's test files. Numbers claimed only in the PR body appear attributed ("PR body reports:
  pytest 161 passed"), never as a verified chip.

## Phase 2 — Understand (before writing a word)

1. **Name the one thing** this PR does, in a single plain sentence. Everything else is a
   detail that hangs off it.
2. **Split the touched files** into production and tests (path holds `test`, `spec`,
   `__tests__`, `.test.`, `.spec.`, or lives under `tests/`). Production files drive Chapter 2;
   test files drive Chapter 3.
3. **Read the production hunks** and write, for each touched non-test file, one plain phrase
   of what changed there — the tree callout. Pick at most **2** hunks that carry the decision
   to show as real diff lines under the tree.
4. **Build the tree** (Chapter 2): the touched subtree only. Group touched files under their
   folders; show a touched file with a `●`, its name in bold, and `+adds −dels`; mark test
   files with a `test` tag and give them no callout. Add a couple of untouched siblings, dimmed
   with `·`, only when they help the reader place the change — do not print the whole folder.
   Cap the tree around 20 rows.
5. **Build the "you are here" strip**: top-level git-tracked directories
   (`git ls-tree -d --name-only HEAD`), byte-sorted, equal-width cells; light the ones that
   contain a touched file. Same strip, same order, every PR — it orients the reader in the
   whole repo without printing it.

## Phase 3 — Write

Draft the prose in a scratch buffer under these rules:

1. **One PR, one thing.** Chapter 1 leads with it. Secondary changes get one line, never an arc.
2. **Every claim points at something the page shows** — a tree callout, a diff line, a gate
   chip, a check, a screenshot. "Faster", "safer", "fixed" each arrive with a number or output.
3. **Concrete before abstract.** The failing command, the error, or the real line comes before
   any statement about it. Examples are trimmed from the actual diff, never invented.
4. **Plain words, ≤ 25-word sentences, one idea per sentence, data over adjectives.**
5. **One name per concept — the name from the code.** Present tense for the new behavior; past
   tense only for what it replaced.

Banned on sight: leverages, robust, seamless, comprehensive, delve, streamlined, powerful,
simply, utilize, facilitate, ensures, significantly, various, clearly, essentially, furthermore,
moreover, "in order to", "it's worth noting", "not only… but also", and "should" when you mean
what the code *does*.

### The bar

The draft leaves Phase 3 only after both gates. Run them in order:

- **Mechanical gate (always).** `wc -w` each chapter and cut anything over budget. `grep` the
  draft for every banned word above and rewrite each hit. Then, **if `vale` is on PATH**, write
  the draft to a scratch `.md` and run `vale --config ~/.claude/at/templates/pr-explain.vale.ini
  <draft>.md` (run `vale --config … sync` once first if `StylesPath` is empty), rewriting every
  alert. `vale` absent or `sync` can't reach the registry → degrade to the `wc` + banned-word
  checks and note it in the report; never fail the run. The banned-word list stays owned by the
  grep; Vale only adds fuzzy prose quality (weasel words, passive voice, wordiness).
- **Critic pass (inline, one rubric, one loop).** Score the draft 0-100, four dimensions ×
  0-25:
  - **Plain & simple** — commonest words; any code word explained once; a first-time reader
    follows it without stopping. This is the point of the page — weight it hardest.
  - **Evidenced** — every claim cites a tree callout / diff line / gate chip / check / screenshot
    the page shows; no unevidenced faster / safer / fixed.
  - **Sharp & short** — clean statements, not bullets and not a wall; ≤ 25-word sentences; every
    chapter within budget.
  - **Complete map & confirm** — the tree marks every touched file with a plain callout (tests
    excepted), and Chapter 5's commands actually confirm *this* change.

  Below **90** → apply the specific misses as one rewrite pass, then re-score once. After the
  rewrite, re-run the banned-word `grep` and per-chapter `wc` — those are hard and must still
  hold at publish.
- **Ship-flag.** Still < 90 after the rewrite → publish anyway and record the final score and
  the unmet dimensions in the report. Never block the publish or loop a third time.

## Phase 4 — Build

- Fill the template's `SLOT` comments. Keep its tokens, classes, and all four theme token
  blocks. Delete the whole `.chapter` div of any chapter you drop. Everything stays inline —
  the artifact CSP blocks external requests.
- **The tree**: use the `.row`, `.dir`, `.file`/`.file.hit`, `.dot`, `.stat`, `.is-test`, and
  `.note` classes exactly as the SLOT comment shows; indent rows with `l1`/`l2`/`l3`. A callout
  is a `.note` row directly under its file.
- Screenshots and e2e output embed as `data:` URIs via `img.evidence`.

## Phase 5 — Publish

- Artifact tool: title `PR #<N> — <plain title, ≤ 8 words>`, favicon `📖` (stable across
  reruns), a one-sentence description.
- Rerun in the same conversation → republish the same file path (same URL). Rerun in a later
  session → pass the teaser's artifact URL (from the Phase 1 body) as the `url` parameter.
  Publishing with `url` fails (artifact deleted or not owned) → publish without it; Phase 6
  rewrites the teaser with the new link.

## Phase 6 — The teaser

Maintain exactly one marker-delimited block in the PR description:

```markdown
<!-- pr-explain:begin -->
### What this PR is for
<the What-this-is-for chapter, verbatim>

**[Read the explainer](<artifact-url>)** · <n> files touched
<!-- pr-explain:end -->
```

- Re-read the body with `gh pr view <N> --json body` — it may have changed since Phase 1.
  Replace the block between the markers in place (append if the markers are absent); write the
  body back with `gh pr edit <N> --body-file <file>`.
- If that fails on a GraphQL `projectCards` deprecation error (a gh quirk on repos with classic
  projects), write the same body with
  `gh api repos/<owner>/<repo>/pulls/<N> -X PATCH -F body=@<file>`.
- Artifact tool unavailable (headless / CI): put the full five chapters, as markdown, between
  the markers in place of the teaser. Say so in your report.
- Never touch prose outside the markers. Empty body → the block is the body.

## Report

End with: the artifact URL, total prose word count, chapters emitted vs dropped, the number of
touched files in the tree, the PR whose teaser you updated, the mechanical gate result (Vale
alerts fixed, or "vale unavailable — wc + grep only"), and the critic score — naming any
dimension left under the bar when the page shipped flagged.
