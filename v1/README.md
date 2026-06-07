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
  ├─ gates      — uv run ruff/mypy/pytest · pnpm exec biome/tsc/vitest · cargo fmt/clippy/check/test  (hard fail, run first)
  ├─ reviewer   — quality + bugs + security on the diff   (is the code good?)
  └─ critic     — goal-fit on the task spec               (did it achieve the task?)

  → objective gates run before the judges; one batched fix round, then re-verify in proportion
    to the change (gates always; scoped re-review; critic only on behavioral change)
  → done only when: all behaviors green, gates green, no CRITICAL, no unwaived review finding ≥70, critic=achieved
```

`architect` is a **skill** invoked explicitly in the main loop (`disable-model-invocation:
true`, so it never auto-triggers), which lets it orchestrate, collect results, and loop.
`worker-coder` (the GREEN/REFACTOR/non-behavioral coder), `tdd-runner`, `reviewer`, `critic`
are **agents** (isolated, scope-locked workers it dispatches via the Agent tool).

## Task contract

v1 expects a scoped task, not an idea. A valid dispatch names:

- `task_id` and `base` (`origin/main`, a SHA, or another merge-base)
- target cwd, absolute `v1_root`, and writable `run_root`
- one module boundary (`module` plus `allowed_paths`)
- task type: `behavioral` or `non_behavioral`
- public interface or exact files in scope
- acceptance criteria / behavior list
- language gate profile(s), plus any project-specific gate overrides
- whether dependencies are allowed

Example:

```yaml
task_id: feat_cart_discount
target_cwd: /abs/project
v1_root: /Users/alf/dev/agent-templates/v1
run_root: /abs/project/.v1-runs
base: origin/main
module: cart
allowed_paths:
  - cart.py
  - tests/test_cart.py
type: behavioral
public_interface: Cart.total(discount: Percent) -> Money
acceptance:
  - Empty cart total remains zero.
  - A ten percent discount on a subtotal of 150 returns 135.
gate_profiles: [python]
verification: uv run pytest tests/test_cart.py
dependencies_allowed: false
```

## Layout

```
v1/
├── README.md
├── rules/                      # the contract every agent reads
│   ├── design-principles.md    #   language-agnostic: deep modules, naming, complexity (Ousterhout)
│   ├── tdd.md                  #   red→green→refactor, vertical slices, public-interface tests
│   ├── python.md               #   language idiom + tooling (copied from repo root)
│   ├── typescript.md           #   "
│   └── rust.md                 #   "
├── agents/
│   ├── worker-coder.md         # GREEN / REFACTOR / non-behavioral; commits; scope-locked
│   ├── tdd-runner.md           # RED: one failing test, right reason; no production code
│   ├── reviewer.md             # quality / bugs / security; reports, doesn't fix
│   └── critic.md               # goal-fit score + verdict
├── schemas/                    # authoritative return-shape contracts (architect validates against these)
│   ├── _defs.schema.json       #   shared schema_version + command def ($ref'd by the others)
│   └── {coder,tdd-runner,reviewer,critic}.schema.json
├── scripts/                    # stdlib-only helpers — no third-party deps
│   ├── validate_return.py      #   validate one agent return against its schema (used by architect)
│   └── check_prompt_schemas.py #   anti-drift: prompt examples vs schemas (python3 scripts/check_prompt_schemas.py)
├── skills/
│   └── architect/SKILL.md      # the driver + JSONL logging contract + decision rules
├── gates/                      # declarative hard gates (reuses make-pr gate format)
│   ├── python.json             #   ruff / typecheck / pytest
│   ├── typescript.json         #   biome / tsc / vitest
│   └── rust.json               #   fmt / clippy / check / test
└── runs/                       # gitignored placeholder — real run logs go to <target_cwd>/.v1-runs (run_root), never under v1/
```

## How quality is enforced (two layers)

1. **Hard tooling gates** (`gates/*.json`) — objective, non-negotiable: format, lint,
   typecheck, tests. The architect runs these and will not declare done on a red gate.
2. **Rules the agents read** (`rules/*.md`) — judgment the tools can't enforce: design
   (deep modules, information hiding), readability (naming, comments), and test quality
   (behavior through public interfaces). The reviewer holds the line on these.

## Return contracts

Every agent returns one JSON object whose authoritative shape lives in `schemas/`. Each schema
pins `role` as a `const`, requires every field, and sets `additionalProperties: false`, so a
return must be **filled literally, not improvised**. The architect validates each return with
`scripts/validate_return.py` (stdlib-only — required keys, enums, `const`s, no extra keys) and
treats a failure as a malformed return. The ` ```json ` block shown in each agent prompt is the
same shape for the model to read; `scripts/check_prompt_schemas.py` (run via `python3
scripts/check_prompt_schemas.py`) checks each example's key structure against the schema so a prompt
edit can't silently add, rename, or drop a field (it compares key sets, not enum values or ranges).

## Gate contract

- Gate commands run through the project package manager (`uv run ...`, `pnpm exec ...`,
  `cargo ...`) so they use the tools installed by `setup`, not globals from the shell.
- Gates are config-backed templates. Strict settings live in project config (`pyproject.toml`,
  `tsconfig`, `biome.json`); gate files run those configured tools. If a repository uses
  equivalent project scripts, adapt the gate file before running the workflow and keep the rule
  file aligned with the gate.
- Gate files include `triggers` globs. Config-only edits such as `pyproject.toml` and
  `package.json` still select their language gate.
- `fix` commands are declared for humans and coder fix tasks and may be `null` when no safe
  mechanical fix exists. The architect runs `setup` and `run` only; it does not auto-apply fixes.
- Rules that are not mechanically enforced by gates are enforced by reviewer/critic judgment.

## Logging & validation

The architect appends **one JSONL line per subagent call, TDD skip, and gate run** to
`<run_root>/<run-id>.jsonl` — `{ts, run, step, role, prompt, result, verdict, files, note}`.
The run id is a sanitized branch name or task id. Because the full prompt/result or command
result is captured for every step, a human can replay and validate the run afterward.

## Scope of v1 (what's intentionally NOT here)

- **Upstream module/PR decomposition planner** — assumed to have run already.
- **PR green-gate / babysit** (CI watch, auto-fix on red) — Phase 3.
- **Workflow-engine port** — once the prompts stabilize, the architect's loop can move to a
  deterministic Workflow script for free journaling + resumability. v1 uses the skill form
  so it's interactive and easy to iterate.
