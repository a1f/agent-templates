# v1 — Coding Workflow

A deterministic, TDD-first pipeline for taking **one scoped PR (one module)** to done, with
every subagent call logged for after-the-fact validation.

This is the **per-PR engine** only. Deciding *which* work becomes a PR — decomposing a
feature into one-module-per-PR tasks — is the job of an upstream planner that is **not part
of v1**. v1 assumes it is handed a single, already-scoped task.

## The pipeline

```
architect (skill, the driver)
  │  intake → restate goal + public interface (must be single-module)
  │  plan behaviors as vertical slices (tdd.md)
  │
  ├─ per behavior:   tdd-runner ──RED──►  coder ──GREEN──►  (coder refactor, optional)
  │                   (one failing       (minimal code,
  │                    test, right        commit)
  │                    reason)
  │
  ├─ reviewer   — quality + bugs + security on the diff   (is the code good?)
  ├─ critic     — goal-fit on the task spec               (did it achieve the task?)
  └─ gates      — ruff/mypy/pytest · biome/tsc/vitest      (hard fail)

  → done only when: all green, no CRITICAL, critic=achieved, gates green
```

`architect` is a **skill** (it runs in the main loop so it can orchestrate, collect results,
and loop). `coder`, `tdd-runner`, `reviewer`, `critic` are **agents** (isolated, scope-locked
workers it dispatches via the Agent tool).

## Layout

```
v1/
├── README.md
├── rules/                      # the contract every agent reads
│   ├── design-principles.md    #   language-agnostic: deep modules, naming, complexity (Ousterhout)
│   ├── tdd.md                  #   red→green→refactor, vertical slices, public-interface tests
│   ├── python.md               #   language idiom + tooling (copied from repo root)
│   └── typescript.md           #   "
├── agents/
│   ├── coder.md                # GREEN: minimal code to pass, commit; scope-locked
│   ├── tdd-runner.md           # RED: one failing test, right reason; no production code
│   ├── reviewer.md             # quality / bugs / security; reports, doesn't fix
│   └── critic.md               # goal-fit score + verdict
├── skills/
│   └── architect/SKILL.md      # the driver + JSONL logging contract + decision rules
├── gates/                      # declarative hard gates (reuses make-pr gate format)
│   ├── python.json             #   ruff / typecheck / pytest
│   └── typescript.json         #   biome / tsc / vitest
└── runs/                       # per-PR JSONL logs (gitignored) — written at runtime
```

## How quality is enforced (two layers)

1. **Hard tooling gates** (`gates/*.json`) — objective, non-negotiable: format, lint,
   typecheck, tests. The architect runs these and will not declare done on a red gate.
2. **Rules the agents read** (`rules/*.md`) — judgment the tools can't enforce: design
   (deep modules, information hiding), readability (naming, comments), and test quality
   (behavior through public interfaces). The reviewer holds the line on these.

## Logging & validation

The architect appends **one JSONL line per subagent call** to `runs/<pr-id>.jsonl` —
`{ts, pr, step, role, prompt, result, verdict, files, note}`. Because the full prompt and
the full result are captured for every dispatch, a human can replay and validate exactly
what each agent was asked and what it returned, without having driven the run live.

## Scope of v1 (what's intentionally NOT here)

- **Upstream module/PR decomposition planner** — assumed to have run already.
- **PR green-gate / babysit** (CI watch, auto-fix on red) — Phase 3.
- **Workflow-engine port** — once the prompts stabilize, the architect's loop can move to a
  deterministic Workflow script for free journaling + resumability. v1 uses the skill form
  so it's interactive and easy to iterate.

## Open reconciliation

`python.md` specifies `mypy --strict`; the copied `gates/python.json` runs `pyright`. Pick
one when wiring gates for real (recommendation: `mypy --strict`, to match the rule).
