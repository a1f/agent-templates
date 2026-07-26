---
name: pr-explain
description: Use when the user invokes /pr-explain or wants a reader-facing explainer page for a pull request — a plain-words page with five chapters (what & why, a walkthrough of the whole diff, every test enumerated, the proof, and confirm commands run with their real output), published as a private claude.ai artifact with a teaser in the PR body.
argument-hint: "[#N | PR URL | blank = current branch's PR]"
---

# PR Explain

Write the page you would produce pair-programming with the person who owns this repo:
you at the keyboard, walking them through the change you just made. They want to keep a
clear mental model of code that agents typed. They are not hunting for bugs — a reviewer
does that. They want to *understand the whole change*, not a sampler of it.

Three rules run through the whole page:

- **Plain words.** Say it the way you would to a smart friend who has not seen the code.
  If a code word is the only word that fits (`hash`, `symlink`, `CI`), say what it does in
  plain words right after — once. Short sentences, one idea each. Active voice. Talk to the
  reader: "you", "your". Start with the point; no wind-up.
- **The whole diff.** Every change in the PR is either shown and explained or named in a
  roll-up line. A reader who finishes the walkthrough has seen the change — never two
  excerpts from a hundred-line diff.
- **Nothing unrun.** Output on the page is output you captured. Proof is something that
  actually executed. If no proof can be written for a behavior change, the page says so —
  that is a finding about the PR, not a gap to pad over.

## Arguments

| Form | Meaning |
|------|---------|
| *(blank)* | The open PR for the current branch |
| `#N` or `N` | PR number in the target repo |
| a PR URL | That PR |

## Runtime resolution

- **Template**: `~/.claude/at/templates/pr-explain-page.html` — design tokens plus the
  `.bottomline`, `.goals`, `.tree`, `.hunk-head`, `.testlist`, `.wit`, `.gate-chip`,
  `.no-proof`, and `.cmd` classes the chapters use. Missing? Still ship: build a
  single-file HTML page with inline CSS that follows the chapter contract. Visual polish
  degrades; the contract does not.
- **Vale config**: `~/.claude/at/templates/pr-explain.vale.ini`, staged with the template. It
  names the write-good / proselint / Google packages the mechanical prose gate runs. Missing,
  or `vale` not installed → the gate degrades to the `wc` + banned-word checks.
- **Page file**: write the filled page to the session scratch directory (never the target
  repo) as `pr-<owner>-<repo>-<number>.html`, owner/repo parsed from the PR's `url`.
- **Target repo**: the git repo of the working directory; run every `gh`/`git` command there.

## The page — five chapters

The shape follows what the big open-source repos converged on for PR descriptions —
Kubernetes ("what this PR does / why we need it"), Google's CL guide (a standalone
imperative first line), React ("the exact commands you ran and their output") — retold in
plain words. Each chapter answers one question. A budget is a ceiling, not a target; drop
an empty chapter, never pad it.

| # | Chapter | The question it answers | Budget |
|---|---------|-------------------------|--------|
| 1 | What & why | What does this PR do, why now, and what is true after it merges? | ≤ 80 words |
| 2 | The walkthrough | What did we change, where is it, and why — across the whole diff | ≤ 40-word note per hunk |
| 3 | The tests | Which tests pin this, one by one, and how they went RED then GREEN | one ≤ 14-word line per test |
| 4 | The proof | What actually ran against this change, with real numbers | 40–70 words + evidence |
| 5 | See for yourself | What can you paste to confirm it — with the output we got | ≤ 40 words + run blocks |

Prose scales with the diff: chapters 1, 4, and 5 keep fixed budgets; the walkthrough grows
one note per hunk and the test list one line per test. Code, diffs, trees, command blocks,
captured output, and test names never count as prose. Each diff or command block caps at
12 lines — trim to the lines that carry the decision. A tiny PR with no behavior (docs, a
version bump, one-line config) shrinks to Chapter 1, a one-line tree, and Chapter 5 — no
forced tests or proof; log the shrink and its reason in the report.

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
  `+<lines_added>`, one gate chip per `gates[]` row. **Never invent evidence.**

## Phase 2 — Understand (before writing a word)

1. **Name the one thing** this PR does, in a single plain sentence. Everything else is a
   detail that hangs off it.
2. **Split the touched files** into production and tests (path holds `test`, `spec`,
   `__tests__`, `.test.`, `.spec.`, or lives under `tests/`). Production files drive Chapter 2;
   test files drive Chapter 3.
3. **Take the hunk inventory.** List every hunk in `gh pr diff` (each `@@` block). Classify
   each: a **decision** hunk changes behavior, an interface, or logic — anything you would
   pause on while pair-programming; a **mechanical** hunk is imports, re-exports, wiring,
   formatting, renames, lockfiles. Every decision hunk becomes a walkthrough entry with its
   own diff lines and note. Mechanical hunks roll up into one named line per file ("plus the
   import and route registration"). Shown or named — those are the only two options; a hunk
   that is neither is a completeness failure the gate below catches.
4. **Order the walkthrough by the call path**, not by filename: start where the request or
   call enters and follow it down (route → interface → storage), the way you would narrate it
   at the keyboard.
5. **Take the test inventory.** For every test file in the diff, list each added or changed
   test by its name in the code. Each becomes one Chapter 3 line.
6. **Build the tree** (Chapter 2): the touched subtree only. Group touched files under their
   folders; show a touched file with a `●`, its name in bold, and `+adds −dels`; mark test
   files with a `test` tag and give them no callout. Add a couple of untouched siblings, dimmed
   with `·`, only when they help the reader place the change — do not print the whole folder.
   Cap the tree around 20 rows.
7. **Build the "you are here" strip**: top-level git-tracked directories
   (`git ls-tree -d --name-only HEAD`), byte-sorted, equal-width cells; light the ones that
   contain a touched file. Same strip, same order, every PR — it orients the reader in the
   whole repo without printing it.

## Phase 3 — Run (capture real output)

Before writing, run the change. Everything here executes in the target repo, on the PR's
head; capture output verbatim for Chapters 4 and 5.

- **Rerun the PR's tests** with the narrowest selector that covers the diff's test files
  (`pytest tests/catalog/ -q`, `cargo test -p <crate>`, `vitest run <dir>`). A fresh green
  run is first-class proof: chip it as `run here — <n> passed`.
- **Run every Chapter 5 command yourself first.** Only ship a command you ran; paste its
  real output next to it. A command the reader needs but you cannot run here (missing
  credentials, no device) ships marked `not run here — needs <thing>`, never with imagined
  output.
- **Safe commands only**: test runners, linters, builds, read-only CLI and `curl` against a
  server you started locally from the repo. Never migrations against shared databases,
  deploys, publishes, or network writes. No documented way to run it → say so and fall back
  to the evidence file and CI.

## Phase 4 — Write

Draft the prose in a scratch buffer under these rules:

1. **One PR, one thing.** Chapter 1 leads with it. Secondary changes get one line, never an arc.
2. **Every claim points at something the page shows** — a walkthrough hunk, a test line, a
   gate chip, captured output. "Faster", "safer", "fixed" each arrive with a number or output.
3. **Concrete before abstract.** The failing command, the error, or the real line comes before
   any statement about it. Examples are trimmed from the actual diff, never invented.
4. **Plain words, ≤ 25-word sentences, one idea per sentence, data over adjectives.**
5. **One name per concept — the name from the code.** Present tense for the new behavior; past
   tense only for what it replaced.

Banned on sight: leverages, robust, seamless, comprehensive, delve, streamlined, powerful,
simply, utilize, facilitate, ensures, significantly, various, clearly, essentially, furthermore,
moreover, "in order to", "it's worth noting", "not only… but also", and "should" when you mean
what the code *does*.

### Chapter 1 — What & why

Three moves, in order, nothing else:

- **One imperative sentence** that stands alone — what this PR does. A future reader finds
  the PR by this line.
- **One or two sentences of why** — what was missing or broken, and why now. From the issue
  or PRD, not the diff.
- **Goals** — two to four short bullets, each an outcome that is true after merge and
  checkable on this page (by a walkthrough hunk, a test line, or a run).

Example shape (not words to copy):

> Add `rate_exercise` and `PUT /api/exercises/{id}/rating` so you can set or clear your own
> rating. Nothing could write the personal rating until now; the tap-to-rate screen (W6) is
> blocked on it.
> **Goals** · a whole number 1–5 sets your rating, `null` clears it · the response returns the
> full exercise, so the screen fetches nothing else · `true` and `"3"` are rejected, not coerced.

### Chapter 2 — The walkthrough

The heart of the page. For each decision hunk, in call-path order:

- a `.hunk-head` line — the file and the function, route, or class the hunk lives in
  ("`api.py` · `PUT /api/exercises/{id}/rating`");
- the trimmed diff lines (≤ 12);
- one note, ≤ 40 words, that answers all three: **what we do** here, **why** it is needed,
  and **where it sits** in the flow ("this runs before any write reaches the database").

Close each file's entries with its mechanical roll-up line if it has one. The tree's
per-file callouts stay — they are the index; the hunks are the walkthrough.

### Chapter 3 — The tests

Enumerate, then witness. First the list: every test from the inventory, grouped under its
file, one line each — the test's name from the code plus ≤ 14 plain words of what it checks.
No test in the diff is left off the list. Then the RED → GREEN story from the witnesses,
verbatim from the evidence file. No evidence file → the list stands alone and the page says
the witnesses are absent.

### Chapter 4 — The proof

Proof is what actually executed, strongest first: your Phase 3 runs, then the evidence
file's gates, then CI checks (`gh pr checks`). Chip each with its real number. Numbers
claimed only in the PR body appear attributed ("PR body reports: pytest 161 passed"), never
as a verified chip.

**The proof gate is hard.** For a PR with behavior, this chapter can neither be dropped nor
padded. If all three sources come up empty — nothing was ever run against this change — the
chapter is the `.no-proof` verdict, verbatim: *"No proof exists: nothing was run to show
this change works. A PR whose proof cannot be written had nothing to prove — that is a
finding about the PR, not this page."* Carry a ⚠ into the teaser and the report. Never
invent a chip to avoid the verdict.

### Chapter 5 — See for yourself

One or two command blocks the reader can paste to confirm *this* change, each followed by
the output you captured in Phase 3. Commands you could not run here carry the
`not run here — needs <thing>` mark instead of output.

### The bar

The draft leaves Phase 4 only after both gates. Run them in order:

- **Mechanical gate (always).**
  - *Coverage*: count hunks (`gh pr diff <N> | grep -c '^@@'`) and check every one is a
    walkthrough entry or inside a named roll-up line. Grep each test name from the inventory
    against the draft; every one appears.
  - *Prose*: `wc -w` each budgeted unit and cut anything over. `grep` the draft for every
    banned word above and rewrite each hit. Then, **if `vale` is on PATH**, write the draft
    to a scratch `.md` and run `vale --config ~/.claude/at/templates/pr-explain.vale.ini
    <draft>.md` (run `vale --config … sync` once first if `StylesPath` is empty), rewriting
    every alert. `vale` absent or `sync` can't reach the registry → degrade to the `wc` +
    banned-word checks and note it in the report; never fail the run. The banned-word list
    stays owned by the grep; Vale only adds fuzzy prose quality.
- **Critic pass (inline, one rubric, one loop).** Score the draft 0-100, four dimensions ×
  0-25:
  - **Plain & simple** — commonest words; any code word explained once; a first-time reader
    follows it without stopping. This is the point of the page — weight it hardest.
  - **Whole diff walked** — every hunk shown or named; each shown hunk's note answers what,
    why, and where; the walkthrough reads in call-path order like a narration.
  - **Enumerated & real** — every test in the diff is on the list with a plain line; every
    output and chip on the page was actually run or quoted from evidence/CI; the no-proof
    verdict, if present, is honest.
  - **Sharp & short** — clean statements; ≤ 25-word sentences; every unit within budget;
    Chapter 1 is the three moves and nothing more.

  Below **90** → apply the specific misses as one rewrite pass, then re-score once. After the
  rewrite, re-run the coverage greps and per-unit `wc` — those are hard and must still hold
  at publish.
- **Ship-flag.** Still < 90 after the rewrite → publish anyway and record the final score and
  the unmet dimensions in the report. Never block the publish or loop a third time.

## Phase 5 — Build

- Fill the template's `SLOT` comments. Keep its tokens, classes, and all four theme token
  blocks. Delete the whole `.chapter` div of any chapter you drop. Everything stays inline —
  the artifact CSP blocks external requests.
- **The tree**: use the `.row`, `.dir`, `.file`/`.file.hit`, `.dot`, `.stat`, `.is-test`, and
  `.note` classes exactly as the SLOT comment shows; indent rows with `l1`/`l2`/`l3`. A callout
  is a `.note` row directly under its file.
- **The walkthrough**: one `.hunk-head` + `.diff` + `.diff-note` group per decision hunk;
  roll-ups are a `.diff-note` alone.
- **The test list**: `.testlist` with a `.tfile` row per file and a `.trow` per test.
- Screenshots and e2e output embed as `data:` URIs via `img.evidence`.

## Phase 6 — Publish

- Artifact tool: title `PR #<N> — <plain title, ≤ 8 words>`, favicon `📖` (stable across
  reruns), a one-sentence description.
- Rerun in the same conversation → republish the same file path (same URL). Rerun in a later
  session → pass the teaser's artifact URL (from the Phase 1 body) as the `url` parameter.
  Publishing with `url` fails (artifact deleted or not owned) → publish without it; Phase 7
  rewrites the teaser with the new link.

## Phase 7 — The teaser

Maintain exactly one marker-delimited block in the PR description:

```markdown
<!-- pr-explain:begin -->
### What & why
<the Chapter 1 summary and why, verbatim>

**Goals**
<the Chapter 1 goal bullets, verbatim>

**[Read the explainer](<artifact-url>)** · <n> files touched
<!-- pr-explain:end -->
```

Chapter 1 doubles as the PR description the big repos would ask for — that is by design.
If the page carries the no-proof verdict, append `· ⚠ no proof — see the explainer` to the
link line.

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

End with: the artifact URL; hunks shown / rolled up / total; tests enumerated; commands run
vs marked not-run; the proof verdict (sources used, or the ⚠ no-proof flag); chapters
emitted vs dropped (with the tiny-PR shrink reason if used); the PR whose teaser you
updated; the mechanical gate result (coverage greps, Vale alerts fixed, or "vale
unavailable — wc + grep only"); and the critic score — naming any dimension left under the
bar when the page shipped flagged.
