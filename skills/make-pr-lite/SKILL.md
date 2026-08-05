---
name: make-pr-lite
description: Use when explicitly asked to run /make-pr-lite on an already-scoped, low-risk single-module PR. A cheaper alternative to /make-pr — one self-TDD coder, the language gates, then a parallel 3-reviewer panel and a critic, squashed to one commit. Not for feature decomposition, multi-module planning, or high-risk work (filesystem/state mutation, merge/refcount, destructive ops) — route those to /make-pr.
argument-hint: "<task spec, issue ref, or path to a task file>"
disable-model-invocation: true
allowed-tools: Read, Write, Bash, Agent, TodoWrite, Skill
---

# make-pr-lite

You orchestrate one already-scoped, low-risk PR to done: dispatch the agents, run the gates,
judge the panel, decide. You never write production code or tests.

## Use it for / route elsewhere

**Use for** greenfield or low-risk PRs: arg routing, parsing, models, read-only views, config, or
code that only composes already-tested units and adds no new state mutation.

**High-risk set → recommend `/make-pr` and stop** (proceed only if the human explicitly confirms
lite for this task): filesystem/state mutation, destructive ops (delete, overwrite, `.bak`
restore), JSON/settings merge-and-unmerge, refcounting, content-hash/drift, or a cutover touching
existing behavior. (Lite verifies a RED's reason but never re-witnesses it live; only `/make-pr`
guarantees that.)

## Runtime resolution

- **skill_root** — the directory this `SKILL.md` lives in; it holds only the SKILL.md itself. The
  rule files and the runtime `gates/` are resolved from `extras_root`, not from here.
- **extras_root** — the installer's state root `~/.claude/at`, the single source of truth the
  installer stages a package's extras into — this skill's `rules/` and `gates/` live here. Resolving
  them from this one root keeps an install self-contained, with no dependency on a repo checkout.
- **rules_root** — `~/.claude/at/rules`, the rules the installer composes from the single canonical
  source; pass rule files as absolute paths (a subagent's cwd is the target repo, so bare names
  won't resolve).
- **target_cwd** — the repo being changed; run every `git`/gate command there.
- **run_root** — `<target_cwd>/.v1-runs`, writable; lite keeps no JSONL log — use `Write` only
  for the `evidence/<branch-slug>/` handoff at Done (`branch-slug` = the pushed branch with `/`
  and whitespace → `_` — the key `/pr-explain` joins on).
- **base** — user/spec-named → else `git merge-base HEAD origin/main` → else `… main` → else stop
  and ask.
- **gates** — preflight: pick `~/.claude/at/gates/<lang>.json` by the task's language(s) /
  `allowed_paths`. After the coder runs, re-check against `git diff --name-only <base>...HEAD`. A
  changed language with no profile → stop and report.
- **rules to pass** — always `design-principles.md`; `tdd.md` for behavioral work; the language
  rule (`python.md`/`typescript.md`/`rust.md`) per changed file type.

## Agents

| Agent | Count | Job |
|---|---|---|
| `coder-lite` | 1 (+ fix) | plan behaviors, self-TDD the whole PR, one commit |
| `reviewer` | 3, parallel | the panel — each a focused lens-group |
| `critic` | 1 (+1 on `partial`) | goal-fit: did the PR achieve the task? |

Dispatch the **3 reviewers in one message** (parallel). **Then**, after they return, dispatch the
**critic** — it needs their findings. Each reviewer gets the base ref (it runs
`git diff <base>...HEAD` itself) and the absolute rule paths, with one lens-group emphasized (it
still reports any CRITICAL it sees outside its group). The groups partition the reviewer's five
lenses:
1. **correctness + security** — lenses `bug`, `security`.
2. **rules-conformance + test-form** — lenses `readability`, `test`.
3. **quality** — lens `quality` (covers simplicity/reuse).

The critic gets the task spec, task type (`behavioral` if any slice has a test, else
`non_behavioral`), base, diff, changed test files, the coder's per-behavior RED evidence, the green
gate output, and the reviewers' findings. Each reviewer finding carries a 1–100 `score` and a
`location` (per the reviewer's return); the panel rules below gate on those.

## The loop

1. **Intake.** Restate goal, boundary/`allowed_paths`, interface or files, acceptance criteria,
   language(s), base, `dependencies_allowed`. Missing any → stop for re-scope. High-risk set →
   route per **Use it for / route elsewhere**. `TodoWrite` the steps.
2. **Preflight.** `git status --short` (dirty outside the boundary → stop). Run the gate `setup`
   once. If tests exist, run the test gate for a green baseline ("no tests yet" is neutral, never a
   final pass). A pre-existing, unrelated red → stop and report.
3. **Build.** Dispatch `coder-lite` `mode: build` with full context (goal, boundary,
   allowed_paths, interface, acceptance criteria, base, `dependencies_allowed`, absolute rule
   paths). Require `status: done`, then verify its return:
   - each behavioral slice shows a **right-reason RED**: `behaviors[].red` has a nonzero exit and a
     `key_output` that is an assertion failure or a missing-symbol error naming the interface being
     added (coder-lite's RED rubric defines it). A behavioral slice with `red: null` → route back.
   - the slice files reconcile: `union(behaviors[].files)` equals `files_changed` equals
     `git diff --name-only <base>...HEAD`. Every **logic file** (importable code defining or
     re-exporting a runtime symbol) appears in at least one behavioral (`red ≠ null`) slice; a logic
     file appearing **only** in `red: null` slices → route back (a behavioral change cannot skip
     RED) — unless that slice is a pure rename/move with no content change (`git` shows `R100`).
     `red: null` slices otherwise carry only declared formats (toml/yaml/ini/json/md).
   - `new_dependencies` empty unless allowed/named → else route back.
   - `blocked` → decide (re-scope, re-dispatch, or stop).
   Max 2 build re-dispatches, then stop and report to the human.
4. **Reproduce + gate (objective — before any judgment).** First re-run the full suite yourself on
   HEAD and route on its outcome; once the suite is green, run the gate profile (`setup` once, then
   each `gates[].run` in order) and route on each gate's outcome. **All gates must pass before the
   panel.** Max 2 fix rounds here, then stop. The table is total — every outcome has a row:

   | Outcome | Action |
   |---|---|
   | suite green **and** every non-null `behaviors[].test` passes | run the gate profile |
   | suite red, or a new test missing/failing | `coder-lite` `mode: fix` — behavioral regression |
   | collection error naming a missing third-party dep | run gate `setup` once, re-run; still missing → `mode: fix` if the dep is approved, else stop and report (scope) |
   | collection error naming a project module under change | `mode: fix` — build failure |
   | a `format`/`lint`/`type` gate red | `mode: fix` — mechanical |
   | the `test` gate red | `mode: fix` — behavioral regression |
   | any other gate red | `mode: fix` — mechanical; name the gate |
   | gate `setup` itself fails | stop and report (environment, not a coder bug) |
5. **Panel + critic (judgment — once, on the green diff).** Dispatch the 3 reviewers (one message),
   then the critic; read the returns directly. Each finding's `score` is severity (1–100, higher =
   worse). **Deduplicate by `(file:line)`** (fall back to `(file:issue)` when a finding has no line),
   keeping the highest-scoring per location. Then block if any row fires:

   | Condition | Result |
   |---|---|
   | any finding CRITICAL, `score >= 70`, or a reviewer's `has_critical` | block |
   | summed `score` of `50–69` findings `>= 120` | block (findings `< 50` are advisory, never aggregate) |
   | critic verdict `not_achieved` | block |
   | critic verdict `partial` | dispatch one second critic; block only if it also returns `partial`/`not_achieved` |

   CRITICAL, a red gate, and a black-letter language-rule violation are **never waivable**. No
   blockers → **Done**.
6. **Fix once, re-verify in proportion.** Capture `git rev-parse HEAD` as `<pre_fix>`, then route
   all blockers back as one batched `coder-lite` `mode: fix` (findings verbatim). After it lands:
   **always** re-run the gates; re-review the fix with the reviewer(s) whose lens-group covers each
   routed blocker, passing `<pre_fix>` as the diff base so they see only the fix's hunks
   (`git diff <pre_fix>...HEAD`); re-run the critic **only if** the fix changed behavior or
   coverage. One fix round (separate from step 4's budget); a second only if round 1 introduced a
   new blocker.
   Then Done, or escalate the remainder to the human as waive-or-rescope.
7. **Done.** When all behaviors and gates are green, no CRITICAL / `>=70` / aggregate blocker, and
   critic `achieved`. **Squash to one commit:**
   `git reset --soft <base> && git commit -m "<conventional subject>"` (no AI attribution).
   Confirm only boundary files changed (`git diff --name-only <base>...HEAD`). Write the evidence
   handoff `<run_root>/evidence/<branch-slug>/evidence.json` (schema
   `~/.claude/at/schemas/evidence.schema.json`; `pipeline: "make-pr-lite"`): one `behaviors[]`
   entry per slice — `name`, `test`, `files`, `red` verbatim from the coder's return, `kind` =
   `behavioral` iff `red` is non-null; `green` = your step-4 suite re-run (`cmd`, `exit_code`,
   `key_output`) with `lines_added` summed from `git diff --numstat <base>...HEAD -- <the
   slice's non-test files>`, or `null` for every slice sharing a production file with another
   slice (a shared file makes per-slice counts non-derivable; never double-count) — plus one
   `gates[]` entry per gate in the final green pass with its
   real `key_output` numbers, and one `runtime[]` entry per capture of the change actually
   working — the branch is built right now, so for a behavioral run drive the built artifact
   end to end (`kind: "run_output"`, real data seeded) and screenshot anything a person looks
   at that now comes out different; each entry carries `kind`, `what`, the `cmd`, and either
   verbatim `key_output` or a `path` copied into `.../runtime/`. `/pr-explain` scores these,
   and its proof chapter values tests plus gates at 7 of 100. `[]` only when the slice is
   non-behavioral or nothing can be launched here — say which in the summary.
   Validate it:
   `uv run --no-project --with jsonschema python ~/.claude/at/scripts/validate_return.py ~/.claude/at/schemas/evidence.schema.json <that file>`
   — a failing file blocks the push. Then ship it
   without asking: branch first if still on the default branch, `git push -u origin <branch>`
   (`--force-with-lease` only if this run already pushed the branch before the squash), and
   `gh pr create` against the default branch (or the task-named target), referencing the
   task/issue in the body. Summarize with the PR URL — done needs no human confirmation. Then
   invoke the `pr-explain` skill (Skill tool, args: the new PR number) — it publishes the
   explainer page from the evidence handoff and maintains the PR-body teaser; headless it
   degrades to markdown in the body on its own, so never skip it; a failure goes in the summary
   and never reopens done.

## Status table

Keep a live table, one row per behavior, plus a panel-scores line after step 5. Example:

```
| B1 discount applies to subtotal | RED✓ | GREEN✓ | gate✓ | panel: 0 blockers |
```
