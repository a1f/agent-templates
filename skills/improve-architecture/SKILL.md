---
name: improve-architecture
description: Use when the user wants to audit a codebase or subsystem for module-decomposition improvements — whether to split, merge, extract, move, delete, or deepen a module to cut complexity — or invokes /improve-architecture.
---

# Improve Architecture

Audits a subsystem and proposes one named **operation per module**, each earned — or
killed — by a caller list re-traced blind.

**Proposes, never edits** — `reviewer` and `critic` judge a diff; this audits existing
code, seeding `/breakdown` or `/make-pr` on approval.
**Rubric: `rules/design-principles.md`** — defines *deep* vs *shallow* and every red
flag or principle below.

```
/improve-architecture [path/subsystem] [--write-issue]

  1. Scope + inventory + load the rubric        (ask if no path)
  2. Sweep clusters, then a cross-cluster pass   (read-only subagents)
  3. Blind re-trace, verify, kill the weak       (fresh skeptic per survivor)
  4. Rank → findings.md, or report clean         (gate: you pick)
  5. Grill the winner, then hand it off           (/breakdown or /make-pr)
```

## The operations

Every finding is one operation anchored on a **primary module** (naming its
counterpart for MERGE/MOVE/EXTRACT) — never "improve this"; the red flag is its
evidence.

| Op | Propose when… | Red flag / principle |
|----|---------------|----------------------|
| **SPLIT** | one module owns two jobs that don't share information — its name needs an "and", a flag parameter forks its behavior, or pure logic is tangled with I/O | Multi-concern · Flag parameter · Scattered side effects |
| **MERGE** | two modules are always used together, a thin layer only forwards, or several modules mirror execution order (read→modify→write) and each must know the others' format | Pass-through · Conjoined methods · Temporal decomposition |
| **EXTRACT** *(add)* | the same decision/format is coded in 3+ places, or behavior can't be swapped or tested without editing it in place (no seam) | Information leakage · Repetition · Special-general mixture |
| **MOVE** *(co-locate)* | code that changes together is scattered; gather it without merging interfaces | Change amplification |
| **DELETE** *(remove)* | a module's interface rivals its body and the code is trivial to inline at each caller | Shallow module · Pass-through |
| **DEEPEN** *(reshape in place)* | the job is right but the interface leaks complexity — overexposed options, an error forced onto every caller, or a name that implies behavior it lacks | Overexposure · Define errors out of existence · Non-obvious code |

When two ops fit, prefer the one leaving **fewer, deeper** modules — a shallow
forwarder folds into its one neighbor (`MERGE`) or inlines into many callers
(`DELETE`).

## The three tests — pass on evidence, not assertion

A candidate failing its test is dropped in Phase 3.

- **Deletion test** — remove the module on paper. If *hidden complexity* scatters
  across callers it was **deep** → keep, maybe `DEEPEN`; if only *trivial
  code* scatters it was **shallow** → `DELETE`/`MERGE`. *Evidence:* the
  independently-grepped caller list.
- **Together-or-apart** — `MERGE` only if the whole is simpler than the parts;
  `SPLIT` only if the parts are simpler than the whole. *Falsifier:* one caller that
  uses a piece without the other kills the `MERGE`; a `SPLIT` leaving two shallow
  modules kills the `SPLIT`.
- **Depth ratio** — small interface over much behavior = deep, leave it; use this
  when there are too few callers to run the deletion test. *Evidence:* signature vs.
  body, not line count.

## Phase 1 — Scope, inventory, load the rubric

**Scope first — never audit a whole repo blind.** Take the target from the argument
(path, package, subsystem); if none, ask. If the inventory below would exceed ~6
clusters, sub-partition and audit one per run rather than skim.

Read `rules/design-principles.md`, and `docs/adr/` first if present —
**never re-propose a decision already rejected there**. `CONTEXT.md`, if present,
records the team's own names and each boundary's rationale — propose in their
vocabulary, not yours.

Build the **inventory**: every file / class / exported function in scope with a
one-line *job* (a job needing an "and" is already a `SPLIT` candidate) and its rough
caller count. Group it into **clusters** — a directory, or a set of files that
mostly call only each other — the fan-out unit for Phase 2.

## Phase 2 — Sweep clusters, then a cross-cluster pass

**Fan out read-only subagents, one per cluster** (`Explore` or `general-purpose`,
**never a coder**), in one message, each given the operation table, the three tests,
and the rubric pointer. Each returns candidates as compact findings carrying
**evidence**:

- **Target** (`file:line`), **Op**, **red flag**.
- **Evidence** — callers resolved by symbol grep + import/re-export resolution (LSP
  if available); dependency direction; for `EXTRACT`, the N≥3 duplicate sites. Flag
  dynamic dispatch (DI, polymorphism, names like `get`/`run`) as untraceable. No
  evidence → no candidate.
- **Before → after** — an interface sketch each side, not full code.

Cluster agents see only their own cluster, so `MERGE`/`EXTRACT`/`MOVE` that span
modules are invisible to them. Then run **one cross-cluster pass** — a read-only
subagent that compares the flagged forwarder/duplicate candidates pairwise, scans the
full decision/format inventory for fresh N≥3 duplication (`EXTRACT`) and for code that
co-changes across modules (`MOVE`), keeping its duplication/dependency map (a small
Mermaid graph) for `findings.md`.

## Phase 3 — Blind re-trace, verify, kill the weak

**Default to rejecting — verify by blind re-trace.** Per survivor, spawn a fresh
read-only subagent given only `target · op`, never the reported evidence. Tell it to:

- re-find the claim's evidence **repo-wide** by a path the sweep didn't use
  (LSP/build-graph, or the dynamic-dispatch sites grep can't see): callers for most
  ops, both modules' for `MERGE`/`SPLIT`, the duplicate sites for `EXTRACT`, the
  co-change set for `MOVE`;
- return its own deletion verdict and leverage band (Phase 4).

**Reject** when any of those diverges enough to flip deep↔shallow or change the band;
an off-by-one edge (a re-export, a test-only site) only downgrades confidence, and
where no path differs from the sweep's grep, cap confidence at **Medium**. Then the
op-specific gate:

- `SPLIT`/`MERGE` — **together-or-apart**, on the re-traced callers.
- `DELETE`/`MERGE` — reject if the **deletion test** comes back deep; confirm the
  boundary isn't an **intentional seam** (port/adapter, public API, extension point).
- `EXTRACT` — reject unless changing the format would force editing all N≥3 sites
  (only co-varying sites count); textual look-alikes don't.
- `MOVE` — reject unless the gathered code actually co-changes (shared change-reason
  or git co-change history).
- `DEEPEN` — reject unless it names ≥2 callers whose code simplifies under the new
  interface.

## Phase 4 — Rank and report (gate)

**If nothing survives, report "no high-leverage operations found in `<scope>`" and
stop — no file.** Never manufacture findings.

Otherwise **sort by leverage, break ties by confidence, drop Low/Low**:
- *Leverage* — by sites the op simplifies (call sites, or duplicate sites for
  `EXTRACT`): High = 5+, or a whole shallow layer removed; Medium = 2–4; Low = one.
- *Confidence* — High = a matching re-trace and a provably complete caller set;
  Medium = partial trace, an off-by-one edge, or unprovable completeness; Low =
  rests on untraceable dynamic dispatch.

Write `findings.md`, one block per surviving candidate:

```
### <n>. <OP> <module>   — leverage <H/M/L> · confidence <H/M/L>
<red flag> — <one-line why it trips>
Evidence: <callers / dep direction / N sites>
Before: <interface sketch>   →   After: <interface sketch>
Effort: <boundaries crossed; slice any >~200 LOC>   ·   Depth: <deep / shallow>
```

Lead each headline with its op and the count it kills. **Gate: nothing is acted on
until you pick** — and a Low-confidence or grep-only winner can't win until you
confirm its trace by spot-checking its call sites. Only the pick is grilled (Phase 5);
the rest ship their *After* sketch unvetted. `--write-issue` also publishes the ranked
list (with the dep-map) as a GitHub issue (needs `gh` + a remote).

## Phase 5 — Grill the winner, then hand it off

**Before handoff, try to break the proposed *After* on paper.** The audit proved the
*current* shape wrong; a fresh skeptic now checks the *After* — does it stay simple at
call sites, hide the decision fully, and add no special case? For a module-boundary
op, sketch two *After* options (design it twice). If it buckles, redesign with the
user before any PR opens. Only then:

- A multi-module reshape (several PRs) → `/breakdown` → PRD → slices → PR rows.
- A single scoped refactor (one ~100–200 LOC PR) → `/make-pr`.

Seed the pipeline with the candidate's *target · op · evidence · before→after* so it
starts test-first from the audit. After handoff, offer to record the new boundary in
`CONTEXT.md` — and any durably-rejected candidate under `docs/adr/` — so the next run
skips re-proposing it.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Verifying against the candidate's own evidence | Blind re-trace: a fresh subagent gets only `target · op` and re-derives the verdict (Phase 3) |
| Deleting or merging an intentional seam | Confirm it isn't a contract or extension boundary first |
| Per-cluster sweep misses MERGE/EXTRACT/MOVE | Run the cross-cluster pass before ranking (Phase 2) |
| High confidence on an unprovable trace | Cap at Medium; dynamic dispatch caps at Low |
| Manufacturing findings to fill the file | Report "clean" and stop when nothing survives |
