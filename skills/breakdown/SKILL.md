---
name: breakdown
description: Use when the user wants to turn a discussion into a published plan — a short PRD, vertical slices, and a PR breakdown, all in one growing GitHub issue — or invokes /breakdown.
---

# Breakdown

Run the full planning pipeline — **PRD → slices → PR breakdown** — into **one
growing GitHub issue**, pausing at each gate. Composes `to-prd`, `to-issues`, and
`pr-breakdown`, each invoked directly.

```
/breakdown [description or context] [--title="..."] [--label=Plan]

Phase 1: to-prd       → creates the issue   (gates: clarify, approve)
Phase 2: to-issues    → appends slices                 (gate: discuss)
Phase 3: pr-breakdown → appends PR rows + PR-map artifact (gate: approve)
```

Run the phases in order; start each only after the previous reports success.
The gates live inside each sub-skill — you just relay their results. A sub-skill
that ends without its success line declined a gate: stop and report.

## Phase 1 — PRD

Invoke `to-prd` via the Skill tool. Pass the user's `[description or context]` and
any `--title` / `--label`. Capture `N` from its final line —
`PRD published: <url> (issue #N)`. If `to-prd` reports a declined gate (no issue
published), stop. If it published but the line won't parse, confirm `N` with the
user before continuing.

## Phase 2 — Slices

Invoke `to-issues` with `--issue=N`. It appends the slice plan and reports
`Slices appended to issue #N`. Proceed on that; stop if it reports a declined gate.

## Phase 3 — PR breakdown

Invoke `pr-breakdown` with `--issue=N`. It appends the PR rows, publishes the
PR-map artifact, and reports `PR breakdown appended to issue #N` with the map URL —
relay that URL. Stop if it reports a declined gate.

## If a gate is declined or a phase fails

Stop and report. Whatever already completed stays valid: a declined Phase 1
leaves nothing, Phase 2 leaves the PRD, Phase 3 leaves PRD + slices — any is a
fine stopping point.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Not threading `--issue=N` into Phases 2–3 | Capture `N` from Phase 1 and pass it on |
| Nesting skills (skill → skill → skill) | Invoke each phase's skill directly |
