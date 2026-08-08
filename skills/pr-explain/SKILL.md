---
name: pr-explain
description: Use when the user invokes /pr-explain or wants a reader-facing explainer page for a pull request. It is a plain-words page with five chapters. They are: what & why, a walkthrough of the whole diff, every test enumerated, a scored proof, and confirm commands run with their real output. It is published as a private claude.ai artifact with a teaser in the PR body.
argument-hint: "[#N | PR URL | blank = current branch's PR] [--confirmed \"<what you saw>\"]"
---

# PR Explain

Write the page you would produce pair-programming with the person who owns this repo:
you at the keyboard, walking them through the change you just made. They want to keep a
clear mental model of code that agents typed. They are not hunting for bugs — a reviewer
does that. They want to *understand the whole change*, not a sampler of it.

Three rules run through the whole page:

- **Plain words.** The `english` rule governs every word on the page — it loads each
  session, so you already have it. Say it the way you would to a smart friend who has not
  seen the code. If a code word is the only word that fits (`hash`, `symlink`, `CI`), say
  what it does in plain words right after — once. Talk to the reader: "you", "your".
- **The whole diff.** Every change in the PR is either shown and explained or named in a
  roll-up line. A reader who finishes the walkthrough has seen the change — never two
  excerpts from a hundred-line diff.
- **Proof is scored, not asserted.** Output on the page is output you captured. Every
  piece of it sits on the ladder below, carrying its points. A reader sees at a glance
  whether this change was watched working or merely compiled. "All tests passed" is the
  weakest sentence on the page, never the proof.

## Arguments

| Form | Meaning |
|------|---------|
| *(blank)* | The open PR for the current branch |
| `#N` or `N` | PR number in the target repo |
| a PR URL | That PR |
| `--confirmed "<what you saw>"` | Fills the ladder's top row — you ran this change yourself. Quoted verbatim, dated today. Combines with any form above |

## Runtime resolution

- **Template**: `~/.claude/at/templates/pr-explain-page.html` — design tokens plus the
  `.bottomline`, `.goals`, `.tree`, `.hunk-head`, `.testlist`, `.wit`, `.score`, `.rung`,
  `.short-proof`, `.gate-chip`, `.no-proof`, `.ba-label`, and `.cmd` classes the chapters
  use. Missing? Still ship: build a
  single-file HTML page with inline CSS that follows the chapter contract. Visual polish
  degrades; the contract does not.
- **Vale config**: `~/.claude/at/templates/pr-explain.vale.ini`, staged with the template. It
  names the write-good / proselint / Google packages the mechanical prose gate runs. Missing,
  or `vale` not installed → the gate degrades to the `wc` + banned-word checks.
- **Page file**: write the filled page to the session scratch directory (never the target
  repo) as `pr-<owner>-<repo>-<number>.html`, owner/repo parsed from the PR's `url`.
- **Target repo**: the git repo of the working directory; run every `gh`/`git` command there.

## The page — five chapters

The shape follows what the big open-source repos converged on for PR descriptions,
retold in plain words. Kubernetes gives "what this PR does / why we need it", Google's
CL guide a standalone imperative first line, React "the exact commands you ran and
their output". Each chapter answers one question. A budget is a ceiling, not a target;
drop an empty chapter, never pad it.

| # | Chapter | The question it answers | Budget |
|---|---------|-------------------------|--------|
| 1 | What & why | What does this PR do, why now, and what is true after it merges? | ≤ 80 words |
| 2 | The walkthrough | What did we change, where is it, and why — across the whole diff | ≤ 40-word note per hunk |
| 3 | The tests | Which tests pin this, one by one, and how they went RED then GREEN | one ≤ 14-word line per test |
| 4 | The proof | What actually ran against this change, scored on the ladder | 40–70 words + the ladder + evidence |
| 5 | See for yourself | What can you paste to confirm it — with the output we got | ≤ 40 words + run blocks |

Prose scales with the diff: chapters 1, 4, and 5 keep fixed budgets; the walkthrough grows
one note per hunk and the test list one line per test. Code, diffs, trees, command blocks,
captured output, and test names never count as prose. Each diff or command block caps at
12 lines — trim to the lines that carry the decision. A tiny PR with no behavior (docs, a
version bump, one-line config) shrinks to Chapter 1, a one-line tree, and Chapter 5.
Force no tests or proof there; log the shrink and its reason in the report.

## The proof ladder

Chapter 4 scores what actually ran against this change, out of 100. Add up the rows you earned,
each at most once — two screenshots are still 20. One capture may earn several rows when it
proves each independently: a before/after pair of screenshots proves both that the change
happened (25) and that the surface renders (20). The rows are claims, not artifacts.

| Pts | The proof | What earns it |
|----:|-----------|---------------|
| 50 | **The owner ran it** | A human outside this run drove the change and said what they saw. Arrives only through `--confirmed` — never write this row yourself, on any evidence |
| 25 | **Before and after on the real thing** | One command, one seeded state, run on the base and on the head, both outputs shown. The only row that proves the *change* rather than that something ran |
| 20 | **A picture of it running** | A screenshot of the built thing doing its job with real data seeded. Text about a surface is not the surface |
| 15 | **A replay the reader can run** | One deterministic command — a `docker run` on a pinned image, a script in the repo — that reproduces your captured output on their machine |
| 10 | **Real output from the built artifact** | The compiled binary, the booted server, the installed CLI driven end to end here, output verbatim |
| 10 | **Proof it is load-bearing** | The change reverted and the resulting failure captured. The difference between "the new code runs" and "the new code is what does it" |
| 10 | **A number for the claim** | The PR says faster, smaller, fewer — measured on the base and on the head, same input. Only when it claims one |
| 5 | **The tests pass** | RED → GREEN witnesses and a green suite. They assert what we told them to assert. Capped: 800 passing is still 5 |
| 2 | **The gates** | Lint, typecheck, format, build, CI green — all of them together, once. They say it compiles and is tidy |
| 0 | **An assertion** | "Verified", "works as expected", a number claimed only in the PR body. Named on the page as unproven; never a scored row |

**The bar is 30** for a PR with behavior. Tests plus gates come to 7, so the bar cannot be
cleared by the suite alone — that is the point of the number. Phase 3 climbs, Phase 4 scores,
under 30 ships flagged.

## Phase 1 — Gather

```bash
branch="$(git branch --show-current)"           # blank arg; empty output → detached HEAD: stop, ask for #N
gh pr list --head "$branch" --json number,url    # [] → no open PR: stop, ask for #N
gh pr view "<N>" --json number,title,body,url,headRefName,additions,deletions,createdAt,files
gh pr diff "<N>"
gh pr checks "<N>" || true                       # <N> is the PR number you substitute
```

Always pass the explicit `<N>` — a bare `gh pr view` targets the current branch's PR, which
may not be the one you were asked about. `--json files` gives every touched path with its
`additions`/`deletions`; that list builds the Chapter 2 tree.

- **The why (Chapter 1)**: read the issue or PRD the PR body references (`Closes #N` /
  `Refs #N`; prefer `Closes`, first match). Use `gh issue view <N> --json title,body` —
  this repo needs `--json`, and a bare `gh issue view` errors on classic project cards. The reason
  comes from there — the slice/PR row the body names, else the issue's headline problem — not
  from the diff. Nothing referenced → derive it from the PR body and diff, and say so on the
  page.
- **Evidence (Chapters 3-4)**: slug the head branch (`/` and whitespace → `_`) and read
  `<target_repo>/.v1-runs/evidence/<slug>/evidence.json` — the make-pr / make-pr-lite handoff.
  It carries `behaviors[]` (each with a RED and a GREEN witness) and `gates[]` (real gate
  numbers from the run). It also carries `runtime[]`, the ladder rows the pipeline
  already captured. Each one has its `kind`, the `cmd` behind it, and a `path` into that
  dir or verbatim `key_output`. Chapters 3 and 4 quote it verbatim. The RED witness carries the
  failure reason, the GREEN witness what made it pass plus `+<lines_added>`. The gates
  collapse into the ladder's one 2-point row, and each `runtime[]` entry scores its own
  row. **Never invent evidence.** Rows the handoff does
  not carry are rows Phase 3 climbs itself, or leaves unlit.

## Phase 2 — Understand (before writing a word)

1. **Name the one thing** this PR does, in a single plain sentence. Everything else is a
   detail that hangs off it.
2. **Split the touched files** into production and tests (path holds `test`, `spec`,
   `__tests__`, `.test.`, `.spec.`, or lives under `tests/`). Production files drive Chapter 2;
   test files drive Chapter 3.
3. **Take the hunk inventory.** List every hunk in `gh pr diff` (each `@@` block). Classify
   each. A **decision** hunk changes behavior, an interface, or logic — anything you would
   pause on while pair-programming. A **mechanical** hunk is imports, re-exports, wiring,
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
   folders. Show a touched file with a `●`, its name in bold, and `+adds −dels`. Mark test
   files with a `test` tag and give them no callout. Add a couple of untouched siblings, dimmed
   with `·`, only when they help the reader place the change — do not print the whole folder.
   Cap the tree around 20 rows.
7. **Build the "you are here" strip**: top-level git-tracked directories
   (`git ls-tree -d --name-only HEAD`), byte-sorted, equal-width cells; light the ones that
   contain a touched file. Same strip, same order, every PR — it orients the reader in the
   whole repo without printing it.
8. **Spot what a person sees.** Not "does the diff touch a template" — *after this merges,
   does anything a human looks at come out different?* Candidates: a page, a TUI, a chart,
   an email body, the shape of a CLI's output, or a rendered view of data this PR changes.
   That holds even when the rendering file is untouched. A board that now lists 3 rows where
   it listed 48 has changed visibly, and "the page is untouched" is no excuse. Yes → Chapter 4 owes a screenshot of it
   running on this branch, and the before/after pair is there for the taking. Plan now how
   Phase 3 captures both.

## Phase 3 — Run (climb the ladder)

Before writing, run the change. Everything here executes in the target repo, on the PR's
head; capture output verbatim for Chapters 4 and 5. Get the artifact running first, because
four of the rows below reuse that one instance. Then work down them until the score clears 30, and
take every row still cheap to reach after that.

- **Drive the built artifact end to end** (10). Build it, boot it, and put a real request
  through it: the compiled binary, the server on a local port, the installed CLI. Seed real
  data first so the answer is interesting. A test harness exercising the same code is not
  this row — the artifact a user gets is.
- **Capture the before and after** (25). `git worktree add <scratch>/base <base>`, build there,
  run the same command against the same seeded state, keep that output; then run it on the
  head. One command, two outputs, the difference visible. The cheapest large points on the
  ladder and the pair a reader actually believes. Remove the worktree when done.
- **Screenshot what a person sees** (20). Phase 2 spotted a visible surface → launch it on
  this branch (the `run` skill knows the launch patterns) and capture the frame: a
  headless-browser shot for a page, the rendered terminal for a TUI. Seed enough real data
  that the surface shows its job, not an empty frame. Status codes, byte counts, and greps
  prove the server answered; only a picture proves a person sees it. Genuinely cannot launch
  it here → a gap Chapter 4 declares, never a step to skip.
- **Write the replay** (15). Fold the end-to-end run into one command anyone can paste — a
  `docker run` on a pinned image, or a script committed in the repo. Run it once from
  clean to confirm it reproduces. Deterministic or it does not score: pin the image, seed
  fixed data, and keep clocks, ports, and paths out of the compared output.
- **Break it on purpose** (10). `git checkout <base> -- <the production file>`, re-run the one
  command or test the PR makes pass, capture the failure, then
  `git checkout HEAD -- <that file>` to restore. Confirm the tree is clean again before
  writing anything else.
- **Measure the claim** (10). The PR says faster, smaller, fewer → time it or count it on the
  base worktree and on the head, same input, and keep both numbers.
- **Rerun the tests** (5) with the narrowest selector covering the diff's test files
  (`pytest tests/catalog/ -q`, `cargo test -p <crate>`, `vitest run <dir>`).
- **Run every Chapter 5 command yourself first.** Only ship a command you ran; paste its
  real output next to it. A command the reader needs but you cannot run here (missing
  credentials, no device) ships marked `not run here — needs <thing>`, never with imagined
  output.
- **Safe commands only**: test runners, linters, builds, read-only CLI and `curl` against a
  server you started locally from the repo. Never migrations against shared databases,
  deploys, publishes, or network writes. A row you cannot reach safely stays unlit and the
  page says why — never one you assert.

## Phase 4 — Write

Draft the prose in a scratch buffer under these rules:

1. **One PR, one thing.** Chapter 1 leads with it. Secondary changes get one line, never an arc.
2. **Every claim points at something the page shows** — a walkthrough hunk, a test line, a lit
   ladder row, captured output. "Faster", "safer", "fixed" each arrive with a number or output.
3. **Concrete before abstract.** The failing command, the error, or the real line comes before
   any statement about it. Examples are trimmed from the actual diff, never invented.
4. **The `english` rule governs every line** — its word caps, its banned list, its
   anti-overuse clauses. Data over adjectives.
5. **One name per concept — the name from the code.** Present tense for the new behavior; past
   tense only for what it replaced.

Banned here on top of the rule's list: simply, significantly, various, clearly, essentially,
and "should" when you mean what the code *does*.

### Chapter 1 — What & why

Three moves, in order, nothing else:

- **One imperative sentence** that stands alone — what this PR does. A future reader finds
  the PR by this line.
- **One or two sentences of why** — what was missing or broken, and why now. From the issue
  or PRD, not the diff.
- **Goals** — two to four short bullets. Each is an outcome that is true after merge and
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
file, one line each. A line is the test's name from the code plus ≤ 14 plain words of what it checks.
No test in the diff is left off the list. Then the RED → GREEN story from the witnesses,
verbatim from the evidence file. No evidence file → the list stands alone and the page says
the witnesses are absent.

### Chapter 4 — The proof

Score the ladder, then show the evidence — **the evidence itself, in this chapter**. Chapter 5
is what the *reader* can paste; Chapter 4 is what *ran*, and a sentence reporting that a run
happened is not that run. So the strong rows carry their artifact here. The screenshot embeds,
the before/after prints as two labelled blocks, and the replay prints as the one command with
the output it produced. Chapter 5 then points back at it rather than printing it twice.

Open with the score (`the proof — 62 / 100`). Then one `.rung` per ladder row, in ladder
order, each earned row carrying its real number and the command behind it. **Rows you did not
earn stay on the page, unlit, with their points.** An unlit "before and after · 25" tells the
reader what was not done, which is the whole reason the ladder is visible. The gates collapse
into their single 2-point row, chips and all; a red CI check chips `fail`. Numbers claimed
only in the PR body appear attributed in prose ("PR body reports: pytest 161 passed"), never
as a scored row.

**The bar is hard.** Under 30 on a PR with behavior → the chapter opens with the
`.short-proof` banner, naming the score and the cheapest unlit row. A ⚠ carries into the
teaser and the report. Nothing ran at all → the `.no-proof` verdict instead, verbatim: *"No
proof exists: nothing was run to show this change works. A PR whose proof cannot be written
had nothing to prove — that is a finding about the PR, not this page."* Never light a row you
did not earn: a page that scores 7 honestly is worth more than one that lies to clear 30.

**The top row is yours alone.** The owner row renders on every page. It is unlit and explicit
("you have not run this yourself yet") unless this run was given `--confirmed`. Given that
flag, it carries the quoted words and today's date. Never fill it from a PR comment, a review approval,
or something said in chat.

**A visible change needs a picture.** Phase 2 spotted a visible surface → at least one Phase 3
screenshot of it running embeds here (`img.evidence`, `data:` URI). Each carries a one-line
`.evidence-cap` caption naming what the reader is looking at. Rows about the surface — curl
status, byte counts, grep hits — do not substitute. No screenshot → the chapter says which
surface shipped unseen and why, and the same ⚠ carries into the teaser and the report.

### Chapter 5 — See for yourself

One or two command blocks the reader can paste to confirm *this* change, each followed by
the output you captured in Phase 3. A replay already printed in Chapter 4 is named here, not
reprinted. Commands you could not run here carry the `not run here — needs <thing>` mark
instead of output.

### The bar

The draft leaves Phase 4 only after both gates. Run them in order:

- **Mechanical gate (always).**
  - *Coverage*: count hunks (`gh pr diff <N> | grep -c '^@@'`) and check every one is a
    walkthrough entry or inside a named roll-up line. Grep each test name from the inventory
    against the draft; every one appears. Phase 2 spotted a visible surface → grep the page
    for `img.evidence`; zero hits fails the gate unless Chapter 4 carries the declared ⚠.
  - *Proof*: add the points of the lit `.rung` rows and check the total matches the printed
    score. Every scorable row appears, lit or unlit — `grep -c 'class="rung' <page>` is 9; the
    0-point assertion row is prose, never a rung. Under 30 on a behavior PR → `.short-proof` is
    present and the ⚠ is in the teaser. A lit row with no command or artifact behind it: unlight
    it and re-score.
  - *Prose*: `wc -w` each budgeted unit and cut anything over. `grep` the draft for every
    banned word — the `english` rule's list plus the six above — and rewrite each hit. Then
    read the draft once against the rule and fix what it catches. **If `vale` is on PATH**, write the draft
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
    output and lit row was actually run or quoted from evidence/CI; the score is what the lit
    rows add up to; the ⚠ banner or no-proof verdict, if present, is honest.
  - **Sharp & short** — clean statements; ≤ 25-word sentences; every unit within budget;
    Chapter 1 is the three moves and nothing more.

  Below **90** → apply the specific misses as one rewrite pass, then re-score once. After the
  rewrite, re-run the coverage greps, the proof arithmetic, and per-unit `wc` — those are hard
  and must still hold at publish.
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
  roll-ups are a `.diff-note` alone. Diff lines read like an editor. Every token wears its
  syntax color (`tok-kw`, `tok-fn`, `tok-str`, `tok-num`, `tok-type`, `tok-com`). Added and
  deleted lines open with a `.sign` `+`/`−`, and the red/green lives in the line background
  and sign — never in the code text.
- **The test list**: `.testlist` with a `.tfile` row per file and a `.trow` per test.
- **The ladder**: `.score` with the total and its `.bar`, then one `.rung` per row. Earned
  rows carry `.pts`, `.what`, and a `.how` naming the command; unearned rows carry the same
  three with `class="rung unlit"`. Evidence hangs under the row it scores. The screenshot goes
  as `img.evidence` + `.evidence-cap`. The before/after goes as two `.cmd` blocks each opened
  by a `.ba-label`. The replay and the run output go as one `.cmd` block each.
- **Staleness check, on the built file, before Phase 6.** An installed template that lags the
  repo drops whole rule sets silently — the page still validates, and only these greps catch it.
  A stale template is never hand-patched: rebuild from the repo's
  `templates/pr-explain-page.html`.
  - `grep -c -- --syn-kw <page>` → `0` is a template older than the syntax tokens, and every
    hunk renders as flat red and green.
  - `grep -c '\.rung' <page>` → `0` is a template older than the ladder, and Chapter 4 renders
    as unstyled text. Each generation of the template needs its own grep here: add one whenever
    a chapter gains a class the last generation lacked.
  - `grep -c tok- <page>` → every `.diff` block holding code carries at least one token span.
    A block quoting prose (a Markdown file, a plain-text log) is the only allowed zero.
  - `grep -n '\.diff \.\(add\|del\) {' <page>` → neither rule sets `color:`. Red and green
    live in the line background and the `.sign` gutter, never on the code text.

  Any one failing → fix it here. Publishing a flat diff or a bare ladder is a failed run.

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

**[Read the explainer](<artifact-url>)** · <n> files touched · proof <score>/100
<!-- pr-explain:end -->
```

Chapter 1 doubles as the PR description the big repos would ask for — that is by design. The
score rides the link line so the number is visible without opening the page. Under the bar,
append `· ⚠ proof under the bar` to that line; nothing run at all, `· ⚠ no proof — see the
explainer`.

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

End with one line each:

- The artifact URL.
- Hunks shown / rolled up / total, and tests enumerated.
- Commands run vs marked not-run.
- **The proof score out of 100, the rows you lit, and the cheapest unlit row with what it
  would have taken.** Add the ⚠ flag when under the bar or nothing ran.
- Screenshots embedded, or the visible surface that shipped unseen and why (⚠).
- Chapters emitted vs dropped, with the tiny-PR shrink reason if used.
- The PR whose teaser you updated.
- The mechanical gate result: coverage greps, Vale alerts fixed, or "vale unavailable —
  wc + grep only".
- The staleness check: tokens and ladder present, or the stale template you rebuilt from.
- The critic score, naming any dimension left under the bar when the page shipped flagged.
