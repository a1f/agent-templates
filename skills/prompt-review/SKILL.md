---
name: prompt-review
description: Use when the user wants this repo's prompt files — skills, agents, rules, the CLAUDE.md template — reviewed for token cost, clarity, and house shape, with the failures fixed in place, or invokes /prompt-review.
argument-hint: "[--all] [--report-only]"
---

# Prompt Review

Prompts are the product here, and they get worse by growing — a model reading a long file
skips instructions in the middle of it. This reviews prompt files against eight criteria and,
by default, fixes what fails.

**The bar is binary.** Each criterion passes or fails — no scores, no "mostly". Every failure
names the file and the lines, so the author can check it and the fix can be small. A file with
nothing wrong is reported clean, never padded with suggestions.

**Fixes change wording, never behavior** — what a prompt does is off limits; how it says it is
the whole job.

```
/prompt-review [--all] [--report-only]

  1. Scope     prompt files changed vs origin/main   (--all = every prompt file)
  2. Review    eight binary criteria per file
  3. Fix       smallest diff per failure             (--report-only stops here)
  4. Report    findings table, counts, verdict stamp
```

## Phase 1 — Scope

Prompt files are `skills/*/SKILL.md`, `agents/*.md`, `rules/*.md`, and
`templates/CLAUDE.md.template`. Nothing else is in scope.

```bash
git fetch origin main
git diff --name-only origin/main...HEAD
```

Keep the paths matching those four patterns — that is the default scope. `--all` replaces it
with every prompt file in the repo:

```bash
ls skills/*/SKILL.md agents/*.md rules/*.md templates/CLAUDE.md.template
```

No match on the default scope → emit the stamp with zeros (`prompt-review: PASS`, `files: 0
reviewed, 0 fixed`, `delta: 0 → 0 words`) in chat, write it to the PR body when a PR exists
(Phase 4), and stop. A clean branch is not a failure, but it still leaves a greppable stamp.

Record `wc -lw` per file before reading it; Phase 4 reports the delta against it.

## Phase 2 — Review

Read each file whole before judging it — criteria 1, 4, and 6 are claims about the file as a
whole, not about a paragraph in isolation. Then take all eight in order:

| # | Criterion | Fails when |
|---|-----------|------------|
| 1 | **Token cost** | a paragraph teaches Claude something it already knows, restates a line above it, or hedges. Ask of every paragraph: does Claude already know this, and does it justify its token cost? |
| 2 | **Description** | skills and agents only — the frontmatter `description` is vague, states what without when (or when without what), drops the key terms a match depends on, or is not third person. A skill's starts "Use when" |
| 3 | **One default** | a menu of options stands where one default plus an escape hatch would do, or a flag hides two jobs behind one name |
| 4 | **Consistent terms** | one concept goes by two names, or one word means two things in the same file |
| 5 | **Concrete over vague** | output shape is described but never shown; a fragile operation is named but its exact command is not given; a fact that rots (a version, a count, a date) is stated as fixed |
| 6 | **Structure** | a reference points at a file that points at another file (deeper than one level); the file runs over 500 lines; a skill is missing the house anatomy — stance paragraph, numbered phases, a report section, and a common-mistakes table where it earns its place |
| 7 | **House paths** | runtime support (schemas, gates, templates, scripts) is referenced as a copy bundled in the skill directory instead of its staged `~/.claude/at/…` path |
| 8 | **Rules pressed hardest** | `rules/*.md` only — criterion 1 at double strength. A rule file loads every session and dilutes every other rule, so a rule the model already follows fails here and wants deleting |

A failure carries the line range and enough of the text to find it: `rules/python.md:112-119 —
criterion 1: restates the type-hint rule from lines 40-51`. A criterion with no failing lines
passes. A criterion with no subject in the file is not applicable and passes without a findings
row — `rules/*.md` frontmatter carries only `paths:`, the CLAUDE.md template has no frontmatter
and no phases, so neither has a `description` or house anatomy to judge.

## Phase 3 — Fix

The default. `--report-only` skips this phase entirely — nothing on disk changes.

Work one file at a time and make the smallest diff that clears the failed criterion. Reach in
this order: **cut** the lines, **tighten** what survives, **restructure** the section. Cutting
is the fix that works most often; a rewrite that keeps the line count has usually missed the
finding.

Never change what a prompt does. A fix that would drop a step, loosen a gate, rename a flag, or
change what the prompt returns is a behavior change: report it with the change it implies and
leave the file alone. Deleting a rule under criterion 8 counts as wording only when the model's
default behavior already matches that rule — otherwise report it and let the author decide.

Re-check each fixed file against all eight criteria before moving on. A cut can strand a term
(4) or break the anatomy (6).

## Phase 4 — Report and stamp

Two tables in chat. The findings table, one row per failing criterion per file — a file that
passes all eight collapses to a single row reading `all pass`:

| File | Criterion | Lines | Verdict | Action |
|------|-----------|-------|---------|--------|
| `rules/python.md` | 1 token cost | 112-119 | fail | fixed |
| `agents/critic.md` | 3 one default | 44-61 | fail | reported — dropping the mode flag changes behavior |
| `skills/explain/SKILL.md` | — | — | all pass | — |

Then the counts table, one row per file plus a `total` row — the stamp's `delta` line repeats
that total:

| File | Lines | Words |
|------|-------|-------|
| `rules/python.md` | 214 → 201 | 1806 → 1699 |
| `agents/critic.md` | 88 → 88 | 742 → 742 |
| `skills/explain/SKILL.md` | 96 → 91 | 803 → 771 |
| **total** | 398 → 380 | 3351 → 3212 |

Last, the verdict stamp, exactly this block:

```
prompt-review: PASS | FAIL
files: <n> reviewed, <n> fixed
delta: <before> → <after> words
```

PASS only when every criterion passes on every file in scope after the fixes; a failure
reported rather than fixed keeps it FAIL. Future CI greps for this block, so keep the three
lines and their order.

Find the branch's PR with `gh pr list --head "$(git branch --show-current)" --json number,url`.
A PR exists → keep exactly one marker block in its body, replacing the block in place when the
markers are already there and appending it when they are not:

```markdown
<!-- prompt-review:begin -->
<the stamp block>
<!-- prompt-review:end -->
```

Round-trip the body through a scratch file in a session temp location (`"$TMPDIR"`), never a
path inside the repo tree where it could be committed by accident:

```bash
gh pr view <N> --json body --jq .body > "$TMPDIR"/pr-body.md
# splice the stamp between the markers in that file; append the marker block when absent
gh pr edit <N> --body-file "$TMPDIR"/pr-body.md
```

`--jq .body` is what keeps step 1 raw markdown — `--json body` alone writes `{"body":"…"}` and
would overwrite the author's whole body with escaped JSON. Never touch prose outside the
markers. No PR, or `--report-only` → print the stamp in chat for the author to paste, and edit
nothing.

## Eval tasks

Every failing row of the findings table is a candidate golden task for a future eval of this
skill: the same file reviewed again must produce the same finding. The shape:

```json
{"query": "review rules/python.md", "files": ["rules/python.md"], "expected_behavior": ["criterion 1 fails at 112-119 — restates the type-hint rule from 40-51"]}
```

`query` is the run that found it, `files` the paths it read, `expected_behavior` one line per
finding a correct run must produce. v1 defines the shape and writes nothing automatically — hand
a task back only when the user asks for one.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Scoring a file 8/10 | One binary verdict per criterion, each failure naming lines |
| Rewriting a paragraph that passed | Only a failure earns a diff |
| Cutting a step to shorten a file | Wording only — report the behavior change instead |
| Reviewing the whole repo on a two-file branch | Default scope is the branch's changed prompt files; `--all` is opt-in |
| Editing the PR body under `--report-only` | Print the stamp; change nothing |
