# agent-templates

A shareable collection of Claude Code skills, language rules, and templates for code review, PR creation, and repo upkeep.

## Getting Started

Clone the repo and run `./install.sh` once. Everything — skills, agents, rules, hooks,
and package extras — installs globally: each component is staged under `~/.claude/at/` and
symlinked into `~/.claude/{skills,agents,rules,hooks}`.

```bash
git clone <your-repo-url> agent-templates
cd agent-templates
./install.sh                 # install the whole catalog into ~/.claude/
./uninstall.sh               # remove everything (restores any backed-up files)
```

Re-run `./install.sh` after a `git pull` to refresh — or run `./at update` to pull and
refresh installed skills in one step.

For interactive component picking, run `./at install` to open the menu — tabs for Bundles /
Packages / Skills / Agents / Rules / Hooks, with installed items pre-ticked. See
[Advanced: `at` CLI](#advanced-at-cli) below for the full command list.

## Using the Skills

### Prerequisites

| Tool | Required by | Install (macOS) | Install (Debian/Ubuntu) |
|------|-------------|-----------------|--------------------------|
| `git` ≥ 2.5 | `make-pr`, `pr-babysit`, `latest-rebase` | `brew install git` | `apt install git` |
| `jq` | Several skills | `brew install jq` | `apt install jq` |
| `gh` | `make-pr`, `pr-babysit`, `dispatch` | `brew install gh` | `apt install gh` |
| `tmux` | `dispatch` (one window per PR) | `brew install tmux` | `apt install tmux` |
| `uv` | Installer (`at` runs the engine via uv); `scripts/` (agent return-schema checks) | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| `claude` CLI | All skills (the runtime) | Claude Code installer | Claude Code installer |

Verify the installation with `./validate.sh`.

### Per-teammate credential setup

Every teammate runs this once after cloning:

1. **GitHub CLI** — authenticate with the scopes required by `make-pr`:

   ```bash
   gh auth login -s repo,read:project,project
   ```

   Already logged in? Refresh scopes: `gh auth refresh -s read:project,project`.

### Mental model

A skill is a named procedure invoked by typing `/skill-name` in a Claude Code session. Some skills are aliases that dispatch to another skill with identical arguments -- for example, `/pr-make` dispatches to `/make-pr`.

### Your first run

Verify the skills installed correctly:

```bash
ls ~/.claude/skills    # should list make-pr, pr-babysit, pr-make-till-merge, ...
```

Then pick a workflow from the decision tree below -- e.g. `/pr-make-till-merge` on a finished branch.

### Decision tree -- "I have X, I want Y"

| What you have | What you want | Skill |
|---|---|---|
| A finished branch (committed work) | A merged PR | `/pr-make-till-merge` |
| An open PR | A merged PR | `/pr-babysit` |
| A plan whose next PRs are unblocked | All of them started at once | `/dispatch` |

### Other daily tasks

- Rebase onto main: `/latest-rebase`
- Audit a subsystem's module decomposition: `/improve-architecture`

## Components Overview

| Component | Location | Description |
|-----------|----------|-------------|
| **Skills** | `skills/` | Code review, PR creation, and repo upkeep |
| **Language Rules** | `rules/` | Opinionated coding standards for Python, TypeScript, Rust, and C++ |
| **Templates** | `templates/` | Starter CLAUDE.md for new projects |

## Skills

Skills are invoked by typing `/skill-name` in a Claude Code session. They cover code review, PR creation, and repo upkeep.

### End-to-end pipelines

Top-level skills that run full workflows by composing lower-level skills.

| Skill | Command | Purpose |
|-------|---------|---------|
| **pr-make-till-merge** | `/pr-make-till-merge` | Create PR from current branch -> babysit. Composes: make-pr -> pr-babysit |

### Building blocks

| Skill | Command | Purpose |
|-------|---------|---------|
| **make-pr** | `/make-pr` | Drive a scoped task to done via a per-behavior TDD loop (tdd-runner + worker-coder), run gates, then reviewer + comment-reviewer + critic. Best for high-risk work |
| **make-pr-lite** | `/make-pr-lite` | Lighter, cheaper sibling of make-pr for low-risk/greenfield PRs: one self-TDD coder + gates + a parallel review panel (3 reviewers + comment-reviewer) + critic. Trades the live per-behavior RED witness for a test-form review lens |
| **dispatch** | `/dispatch` | Start the unblocked PRs from a plan in parallel — approval-gated, then one tmux window per PR, each in its own worktree running an agent on `/make-pr <ref> <PR#>` |
| **pr-babysit** | `/pr-babysit` | Poll PR until ready to merge, fix review/CI issues |
| **latest-rebase** | `/latest-rebase` | Rebase current branch onto latest main |
| **improve-architecture** | `/improve-architecture` | Read-only audit of a subsystem's module decomposition — ranks SPLIT/MERGE/EXTRACT/MOVE/DELETE/DEEPEN candidates against `design-principles.md` with traced evidence, gates on your pick, hands off to `/breakdown` or `/make-pr` |

**Aliases** (same arguments, alternate slash name): `/pr-make` -> `/make-pr`.

### Planning & course-correction

Turn a discussion into a published plan in one growing GitHub issue, then keep
that plan honest as PRs land.

| Skill | Command | Purpose |
|-------|---------|---------|
| **breakdown** | `/breakdown` | Run the whole pipeline (PRD -> slices -> PR rows) into one issue, gating at each step. Composes the three below |
| **to-prd** | `/to-prd` | Turn the conversation into a short PRD published as a GitHub issue |
| **to-issues** | `/to-issues` | Break the PRD into vertical, tracer-bullet slices in the same issue |
| **pr-breakdown** | `/pr-breakdown` | Split each slice into ~100-200 LOC PR rows in the same issue |
| **course-correct** | `/course-correct` | After some PRs land, check merged work against the PRD goal and re-plan: refresh Status, add/remove/re-scope slices and PRs. Checkpoint-aware; run it in a fresh session every few PRs |
| **explain** | `/explain` | Explain a slice, PR row, or GitHub PR in dead-simple, plain words — why we need it, what it is, what changes — for someone who doesn't code |

## Language Rules

Opinionated coding standards that load automatically when editing matching files — per-language conventions plus three cross-cutting rules (design, TDD, and English).

| Language | File | Target | Highlights |
|----------|------|--------|------------|
| Python | `rules/python.md` | Python 3.12+ | Type hints everywhere, `\|` union syntax, `match`/`case`, no bare `except` |
| TypeScript | `rules/typescript.md` | TypeScript 5.8+ | Strict mode, discriminated unions, `satisfies`, Zod validation |
| Rust | `rules/rust.md` | Edition 2024 | `?` propagation, `impl Trait` params, builder pattern, `#[must_use]` |
| C++ | `rules/cpp.md` | C++20 | Concepts, ranges, `std::format`, smart pointers, RAII |

### Cross-cutting rules

Four language-agnostic rules install alongside the language rules and load on broader globs:

| Rule | File | Loads on | Covers |
|------|------|----------|--------|
| Design principles | `rules/design-principles.md` | any source file | deep modules, information hiding, naming, complexity (Ousterhout) |
| Comments | `rules/comments.md` | any source file | the two comments always allowed, the test for an inline comment, size caps, where the reasoning goes instead, the slop shapes |
| TDD | `rules/tdd.md` | test files | red→green→refactor, vertical slices, public-interface tests |
| English | `rules/english.md` | every file | one word one meaning, simple tenses, 20/25-word sentences, banned words, when a picture earns its place (ASD-STE100) |

### Installation

Rules install globally as symlinks into `~/.claude/rules/` when you run `./install.sh`. Each `rules/*.md` file is staged under `~/.claude/at/` and symlinked into `~/.claude/rules/`, where Claude Code picks it up automatically based on the file type being edited.

## Templates

### Project CLAUDE.md (`templates/CLAUDE.md.template`)

A starter `CLAUDE.md` for new projects — fill in the project name, tech stack, commands, and structure. It documents the skill entry points (`/make-pr`, `/pr-make-till-merge`, the review skills, and the repo-upkeep skills) so Claude Code picks the right workflow. Copy it to your project root as `CLAUDE.md` and edit the placeholders. It is not installed by `./install.sh` — copy it manually.

## Advanced: `at` CLI

The scripts above cover the common case. For anything more specific, use the `at` CLI directly:

- `./at install` — open the interactive menu
- `./at install --all` — install the whole catalog
- `./at install --skill <name>` (or `--agent`, `--rule`, `--hook`, `--package`, `--bundle`) — install named components
- `./at uninstall --all` — remove everything (or the same per-component flags to remove one)
- `./at update` — pull the repo and refresh installed skills
- `./at status` — show the installation dashboard
- `./at validate` — lint the catalog
- `./at --help` — full command reference

## Installation Details

| Component | Install Location | Scope |
|-----------|-----------------|-------|
| Skills | `~/.claude/skills/<name>/` | Global (all projects) |
| Language Rules | `~/.claude/rules/*.md` | Global (all projects) |

Each component is staged under `~/.claude/at/` and symlinked into the matching `~/.claude/` subdirectory. On a collision the existing real file is backed up to `.bak` and restored on uninstall. Install state lives in `~/.claude/at/state.json`.

## Validation

`./validate.sh` lints the catalog without installing anything — it loads `installer/catalog.toml` through the same loader the installer uses and reports what it found:

```bash
./validate.sh    # prints: catalog OK — <N> units, <M> packages, <K> bundles
```

A dangling reference, a missing required key, or a malformed catalog fails with a single error line and a non-zero exit.

The full test suite — unit tests plus an end-to-end smoke of the real shims — runs from the installer project, and CI runs it on every PR:

```bash
cd installer && uv run pytest
```

The agent return-schema check runs standalone:

```bash
python3 scripts/check_prompt_schemas.py
```

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes. If you add a new skill, agent, rule, or hook, register it in `installer/catalog.toml` (a new skill also needs a `SKILL.md` with valid YAML frontmatter).
3. Run `./validate.sh` to lint the catalog.
4. Run `cd installer && uv run pytest` to run the full test suite (unit + e2e smoke of the real shims).
5. Open a pull request with a clear description of the change.

### Authoring a new skill

1. Copy `skills/latest-rebase/` as the minimal template — it has a single `SKILL.md` with the right frontmatter shape and no supporting files.
2. `SKILL.md` frontmatter requires two keys: `name` and `description`. The description **should** start with the literal string `"Use when"` so Claude Code picks the skill reliably — a convention enforced by review, not by `./validate.sh`, which lints only the catalog.
3. Fill in the skill body below the frontmatter. Claude Code loads the body when the user types `/your-skill-name`.
4. Register the skill in `installer/catalog.toml`, then run `./validate.sh` to lint the catalog and `cd installer && uv run pytest` to run the test suite.

### Authoring a rule

Rules are global coding standards that load on matching file edits.

1. Create `rules/<language>.md`.
2. Frontmatter must include `paths:` as a **comma-separated quoted string** — not a YAML array. Example: `paths: "*.py, *.pyi"`, not the `[...]` array form.
3. Register the rule in `installer/catalog.toml`, then run `./validate.sh`.

## License

MIT -- see [LICENSE](LICENSE).
