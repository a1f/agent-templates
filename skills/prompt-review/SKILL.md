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

**The goal is a file a model follows end to end and acts on correctly.** Everything below is a
proxy for that. When two criteria collide, the one that changes how the file is executed wins:
adding a missing default or an exact command is a good fix even though it lengthens the file.
The word delta is a diagnostic, never the target. The test for raising anything at all: would a
model executing this file behave differently if this were fixed? If not, it passes.

**Wording only, no approval gate, re-runnable.** Invoking the skill is the permission to edit;
a second run over a clean file changes nothing. A good run leaves every file doing exactly what
it did before, with the failures wording could close actually closed. Rubric for criteria 4, 5
and 7: `~/.claude/at/rules/design-principles.md`, sections *Avoid flag parameters*, *Naming*,
and *Consistency*.

```
/prompt-review [--all] [--report-only]

  1. Scope the prompt files changed vs origin/main   (--all = every prompt file)
  2. Review each against the eight criteria
  3. Fix what wording can fix                        (--report-only skips 3 and 5)
  4. Report the tables and the verdict
  5. Write the verdict block into the PR body
```

`--report-only` changes what gets written, never how it is judged: the verdict falls out of the
same rule as any other run.

## Runtime resolution

- **Target repo** — the git repo of the working directory. Run every command from its root
  (`cd "$(git rev-parse --show-toplevel)"`); every path below is root-relative. No `skills/`,
  `agents/`, `rules/` or `templates/` there → this is not that repo: say so and stop.
- **Prompt files** — `skills/*/SKILL.md`, `agents/*.md`, `rules/*.md`, and
  `templates/CLAUDE.md.template`. Nothing else is in scope.
- **`$SCRATCH`** — the session scratch directory, which holds the PR-body copy. Never a path
  inside the repo tree, where it could be committed by accident.

## Phase 1 — Scope

```bash
git fetch -q origin
FILES=$(git diff --name-only --diff-filter=d origin/main...HEAD | grep -E \
  '^(skills/[^/]+/SKILL\.md|agents/[^/]+\.md|rules/[^/]+\.md|templates/CLAUDE\.md\.template)$' \
  || true)
```

`--diff-filter=d` drops deleted paths, which cannot be read. `--all` replaces that list:

```bash
FILES=$(ls skills/*/SKILL.md agents/*.md rules/*.md templates/CLAUDE.md.template 2>/dev/null || true)
```

`|| true` keeps an empty match from aborting under a strict shell, but it also hides a real
failure, so confirm the base before trusting an empty result:

```bash
git rev-parse --verify origin/main >/dev/null || { echo "abort: origin/main missing"; exit 1; }
```

Empty `FILES` in either mode is an empty scope: print the verdict block with zeros in chat and
stop, touching no PR body — replacing a real verdict with `0 reviewed` erases a result nobody
re-earned.

Write `FILES` to `$SCRATCH/scope.txt` and re-read it in each later phase — shell variables do
not survive between steps. Then settle in shell everything that does not need a model read:

```bash
while read -r f; do
  wc -lw "$f"                     # Phase 4's before-counts; past 500 lines is the standing finding
  grep -c '^## Phase' "$f"        # criterion 7's phases check
  grep -m1 '^description:' "$f"   # criterion 3 judges this one line, not the file
done < "$SCRATCH/scope.txt" > "$SCRATCH/mechanical.txt"
```

Criterion 1 probes, criteria 2, 4, 5 and 6 need the prose; the rest start from that file. Past
about five files, fan out — one read-only subagent per file, returning its two table rows —
rather than pulling every file into one context, which is the failure this skill exists to
catch. Both tables and the `reviewed` count always cover the full scope, never just the part
that finished.

Record `wc -lw` per file before reading it, and again after its fixes — Phase 4 reports both.

## Phase 2 — Review

Read each file whole before judging it: criteria 2, 5, and 7 are claims about the file as a
whole.

| # | Criterion | Fails when |
|---|-----------|------------|
| 1 | **It works** | an instruction cannot be followed: a command that errors or takes a flag the installed tool lacks, a path that is not there, a shell block that does not parse, a cross-reference that points at the wrong place or needs a third hop to reach the instruction |
| 2 | **Token cost** | a paragraph teaches Claude something it already knows, restates a line above it, or hedges |
| 3 | **Description** | skills and agents only — the frontmatter `description` is vague, states what without when (or when without what), drops the key terms a match depends on, is not third person, or — for a skill — does not open "Use when" |
| 4 | **One default** | a menu of options stands where one default plus an escape hatch would do, or a flag hides two jobs behind one name |
| 5 | **Consistent terms** | one concept goes by two names, or one word means two things in the same file |
| 6 | **Concrete over vague** | output shape is described but never shown; a fragile operation is named but its exact command is not given; a fact that rots (a version, a count, a date) is stated as fixed |
| 7 | **House anatomy** | a skill has no stance paragraph saying what it is for, or its steps are prose where the file's own siblings use numbered phases |
| 8 | **House paths** | runtime support (schemas, gates, templates, scripts) is referenced as a copy in the skill directory when the same asset is staged under `~/.claude/at/…` |

Criterion 1 is checked by probing, never by reading — a command looks fine right up until you
run it. For each file, before judging any prose:

```bash
grep -oE '`[a-z]+ [a-z-]+[^`]*`' <file> | tr -d '`'   # candidate commands to probe
```

Probe each: `command -v <tool>` for the tool, `<tool> <subcommand> --help` for a flag it is
given, `test -e` for every path it names, `bash -n` on every shell block, and open every
cross-reference to confirm it lands where the text says. Criterion 1 outranks the rest: a file
whose instructions do not run is broken however well it reads.

### The two standing findings

Both are recorded in this phase, on the file as it arrives, and neither is ever auto-fixed — a
later fix that changes the count never retracts one.

- **Rule deletion** — `rules/*.md` loads every session and dilutes every other rule, so press
  criterion 1 twice as hard there. The finding is that a whole rule should go; trimming a
  paragraph inside one is an ordinary criterion-2 fix. Whether the model would follow a rule
  unprompted is not something this review can test, so name the rule and let the author decide.
- **Over length** — a file past 500 lines. Cutting one to length is a rewrite, and trimming
  blank lines to clear the number fools only the counter.

A failure carries the line range and enough of the text to find it: `rules/python.md:112-119 —
criterion 1: restates the type-hint rule from lines 40-51`. Line numbers are the ones recorded
in Phase 1, before any fix shifted them. A criterion with no subject in the file is not
applicable and passes without a findings row — `rules/*.md` frontmatter carries only `paths:`,
and the CLAUDE.md template has no frontmatter and no phases.

## Phase 3 — Fix

Work one file at a time and make the smallest diff that clears the failed criterion. Reach in
this order: **cut** the lines, **tighten** what survives, **restructure** the section. A rewrite
that keeps the line count has usually missed the finding.

Never change what a prompt does. A fix that would drop a step, loosen a gate, rename a flag, or
change what the prompt returns is a behavior change: report it with the change it implies and
leave the file alone.

Re-check only what a cut can break — criterion 5, criterion 7, and the one just fixed — against
the changed hunks, not the whole file. Re-check at most twice; a failure still open after that
is reported as `open — re-check cap`, and stays open for the verdict.

## Phase 4 — The tables and the verdict

The findings table carries one row per failing criterion per file, plus one per standing
finding; a file that passes everything collapses to a single row reading `all pass`. The
`Criterion` cell holds a numbered criterion or a standing finding, and `Lines` the failing
range — or the file's length, when that is the finding:

| File | Criterion | Lines | Verdict | Action |
|------|-----------|-------|---------|--------|
| `skills/pr-babysit/SKILL.md` | 1 it works | 154-156 | fail | fixed — `then` branch held only a comment, so `bash -n` failed |
| `rules/python.md` | 2 token cost | 112-119 | fail | fixed |
| `agents/critic.md` | 4 one default | 44-61 | fail | reported — dropping the mode flag changes behavior |
| `skills/pr-babysit/SKILL.md` | over length | 501 | fail | reported — cutting to length is a rewrite |
| `skills/explain/SKILL.md` | — | — | all pass | — |

The counts table carries one row per file in scope — the same files, so both tables and the
verdict's `reviewed` count always agree — plus a `total` row whose words the verdict repeats:

| File | Lines | Words |
|------|-------|-------|
| `rules/python.md` | 135 → 127 | 1228 → 1156 |
| `agents/critic.md` | 85 → 85 | 708 → 708 |
| `skills/pr-babysit/SKILL.md` | 501 → 502 | 4023 → 4028 |
| `skills/explain/SKILL.md` | 117 → 117 | 963 → 963 |
| **total** | 838 → 831 | 6922 → 6855 |

`pr-babysit` got longer, and that is the right outcome: the criterion-1 fix put a real command
in an empty `then` branch. A delta that goes up is not a failed run.

Last, the verdict block — exactly these three lines, in this order, so a future CI gate can
grep it:

````markdown
```
prompt-review: <PASS | REPORTED | FAIL>
files: <n> reviewed, <n> fixed
delta: <before> → <after> words
```
````

Take the first state that applies, judging what is still open once Phase 3 has run. A finding
that was fixed is closed and counts for nothing here:

1. **FAIL** — a failure this skill was allowed to fix is still open. Behavior changes and
   standing findings never qualify: they were never this skill's to fix. A `--report-only` run
   leaves every fixable failure open, so one found is one still open.
2. **REPORTED** — something is left, and all of it is the author's to decide: a behavior change
   or a standing finding.
3. **PASS** — nothing is left open, whether or not anything was fixed, or nothing was in scope.

`fixed` counts files whose bytes changed, not findings closed.

## Phase 5 — Write the verdict block

Skip this phase and print the block in chat — saying which condition skipped it — when
`--report-only` is set, the scope was empty, `gh` is missing, HEAD is detached, or the branch
has no single open PR. The last three skip from inside the block:

```bash
cd "$(git rev-parse --show-toplevel)"; SCRATCH=<the session scratch directory>
command -v gh >/dev/null || { echo "skip: gh missing" >&2; exit 0; }
BRANCH=$(git branch --show-current)
[ -n "$BRANCH" ] || { echo "skip: detached HEAD" >&2; exit 0; }
PR=$(gh pr list --head "$BRANCH" --json number -q 'if length == 1 then .[0].number else "" end')
[ -n "$PR" ] || { echo "skip: no single open PR" >&2; exit 0; }
printf '%s\n' "$PR" > "$SCRATCH/pr-number"
gh pr view "$PR" --json body -q .body | sed -e 's/\r$//' > "$SCRATCH/pr-body.md"
{ [ "$(wc -c < "$SCRATCH/pr-body.md")" -gt 1 ] && [ "$(cat "$SCRATCH/pr-body.md")" != null ]; } \
  || { echo "abort: failed PR body read" >&2; exit 1; }
```

That last guard is why a bare `[ -s ]` will not do: `-q .body` prints the literal `null` for a
null body and a lone newline for an empty one, so both look non-empty to `-s`.

Now read `pr-body.md`, replace what sits between the markers with the verdict block — markers
absent, append it after a blank line — and write the result to `new-body.md` with the Write
tool. Never a heredoc or `sed -i`: both mangle the author's markdown. The block goes in wrapped
and fenced, `<!-- prompt-review:begin -->`, then the Phase 4 verdict block verbatim, then
`<!-- prompt-review:end -->`.

The diff is the gate. Its only legal hunk is that block — every other byte, including any other
skill's markers, stays as the author left it:

```bash
SCRATCH=<the session scratch directory>; PR=$(cat "$SCRATCH/pr-number")
[ -s "$SCRATCH/new-body.md" ] || { echo "abort: empty new body" >&2; exit 1; }
diff "$SCRATCH/pr-body.md" "$SCRATCH/new-body.md"
gh pr edit "$PR" --body-file "$SCRATCH/new-body.md" \
  || gh api "repos/{owner}/{repo}/pulls/$PR" -X PATCH -F body=@"$SCRATCH/new-body.md"
```

The `gh api` fallback is for repos with classic projects, where `gh pr edit` fails on a
`projectCards` deprecation error.

## Report

End with the verdict line, the two tables, and the PR the block landed in — or, when Phase 5
was skipped, which condition skipped it and the block for the author to paste.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Scoring a file 8/10 | One binary verdict per criterion, each failure naming lines (Phase 2) |
| Cutting a step to shorten a file | Wording only — report the behavior change instead (Phase 3) |
| Deleting a rule because the model "already knows it" | Report it; the author owns what leaves a file every session reads |
| Editing the PR body under `--report-only`, or after a zero-scope run | Print the block; change nothing (Phase 5) |
