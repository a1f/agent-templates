---
name: prompt-review
description: Use when the user wants this repo's prompt files — skills, agents, rules, the CLAUDE.md template — reviewed against five checks with the failures fixed in place, or invokes /prompt-review.
argument-hint: "[--all] [--report-only]"
---

# Prompt Review

Prompts are the product here, and they get worse by growing — a model reading a long file
skips instructions in the middle of it. This reviews prompt files against five checks and, by
default, fixes what fails.

**The goal is a file a model follows end to end and acts on correctly.** The checks are proxies
for that. When two collide, the one that changes how the file is executed wins — an exact
command earns its words. Raise nothing that would not change what a model does.

**Wording only.** A fix that drops a step, loosens a gate, renames a flag, or changes what a
prompt returns is a behavior change: report it and leave the file alone. Invoking the skill is
the permission to edit; a second run over a clean file changes nothing.

```
/prompt-review [--all] [--report-only]

  1. Scope   prompt files changed vs origin/main   (--all = every prompt file)
  2. Review  five checks per file
  3. Fix     what wording can fix                  (--report-only skips this)
  4. Report  one table, one verdict
```

## Phase 1 — Scope

Prompt files are `skills/*/SKILL.md`, `agents/*.md`, `rules/*.md`, and
`templates/CLAUDE.md.template`. Nothing else. Run from the repo root.

```bash
cd "$(git rev-parse --show-toplevel)"; SCRATCH=<the session scratch directory>
git rev-parse --verify origin/main >/dev/null || { echo "abort: origin/main missing"; exit 1; }
git diff --name-only --diff-filter=d origin/main...HEAD | grep -E \
  '^(skills/[^/]+/SKILL\.md|agents/[^/]+\.md|rules/[^/]+\.md|templates/CLAUDE\.md\.template)$' \
  > "$SCRATCH/scope.txt" || true            # --all: ls the four patterns instead
xargs -r wc -lw < "$SCRATCH/scope.txt"      # before-counts; over 500 lines is its own finding
```

`--diff-filter=d` drops deleted paths; `|| true` keeps an empty match from aborting a strict
shell. Empty scope → print the verdict with zeros and stop. Past about five files, fan out one
read-only subagent per file, each returning its rows — never pull every file into one context.

## Phase 2 — Review

| # | Check | Fails when |
|---|-------|------------|
| 1 | **It works** | an instruction cannot be followed: a command that errors or takes a flag the installed tool lacks, a path that is not there, a shell block that does not parse, a reference that points at the wrong place |
| 2 | **Fewest words** | a paragraph teaches Claude what it already knows, restates a line above it, hedges, or argues for a rule already stated imperatively |
| 3 | **Sharp and concrete** | an output shape is described but never shown; a fragile operation is named without its exact command; a menu of options stands where one default and an escape hatch would do; a `description` is too vague to match on; a fact that rots is stated as fixed |
| 4 | **Consistent** | one concept goes by two names, one word means two things, or a step is done differently here than everywhere else in the repo |
| 5 | **Effective and efficient** | the file does not actually achieve its stated job, or it makes the model pay for what a shell command settles — a whole-file read where a grep would do, an unbounded probe, a re-read, a loop with no cap |

Check 1 is settled by probing, never by reading — a command looks fine right up until you run
it. Extract the commands and paths from the file's fenced blocks, then `command -v` the tool,
`<tool> <sub> --help | grep -- --flag` for a flag it is given (never the whole help page),
`test -e` every path, `bash -n` every shell block, and open every reference. Check 1 outranks
the rest: a file whose instructions do not run is broken however well it reads.

Two findings are never auto-fixed, only reported: a file **over 500 lines** (cutting one to
length is a rewrite, and deleting blank lines fools only the counter), and **deleting a whole
rule** from `rules/*.md` — that file loads every session, so press check 2 twice as hard there,
but whether the model would follow a rule unprompted is not something this review can test.

A failure names the range and enough text to find it: `rules/python.md:112-119 — check 2:
restates the type-hint rule from 40-51`. Line numbers are Phase 1's, before any fix moved them.
A check with no subject in the file passes without a row.

## Phase 3 — Fix

One file at a time, smallest diff that clears the failure: **cut**, then **tighten**, then
**restructure**. Re-check only what a cut can break — checks 2 and 4, and the one just fixed —
against the changed hunks. Twice at most; a failure still open after that is reported.

## Phase 4 — Report

One table. A file that passes everything collapses to a single `all pass` row; `Check` holds a
number or a standing finding, `Lines` the failing range or the file's length:

| File | Check | Lines | Verdict | Action |
|------|-------|-------|---------|--------|
| `skills/pr-babysit/SKILL.md` | 1 it works | 154-156 | fail | fixed — `then` branch held only a comment, so `bash -n` failed |
| `rules/python.md` | 2 fewest words | 112-119 | fail | fixed |
| `agents/critic.md` | 3 sharp | 44-61 | fail | reported — dropping the mode flag changes behavior |
| `skills/explain/SKILL.md` | — | — | all pass | — |

Then the verdict, exactly these three lines so a future CI gate can grep it:

```
prompt-review: <PASS | REPORTED | FAIL>
files: <n> reviewed, <n> fixed
delta: <before> → <after> words
```

Take the first state that applies, judging what is still open after Phase 3. A fixed finding is
closed and counts for nothing:

1. **FAIL** — a failure this skill was allowed to fix is still open. `--report-only` fixes
   nothing, so one found is one open.
2. **REPORTED** — what is left is the author's to decide: a behavior change or a standing finding.
3. **PASS** — nothing is left open, or nothing was in scope.

`fixed` counts files whose bytes changed. `delta` is a diagnostic, never the target — a fix that
adds an exact command makes the file longer and is still the right fix. No PR is edited: print
the verdict for the author to paste.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Scoring a file 8/10 | One pass-or-fail verdict per check, each failure naming lines |
| Reading a file to decide check 1 | Probe it — run the command, `test -e` the path, `bash -n` the block |
| Cutting a step to shorten a file | Wording only — report the behavior change instead |
| Deleting a rule because the model "already knows it" | Report it; the author owns what leaves a file every session reads |
