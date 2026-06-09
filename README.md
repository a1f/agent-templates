# agent-templates

A shareable collection of Claude Code skills, language rules, and templates for code review, PR creation, and repo upkeep.

## Getting Started

Clone the repo and run `install.sh` twice — once to install the global skills
and once per project to install the per-project language rules:

```bash
git clone <your-repo-url> agent-templates
cd agent-templates
./install.sh                 # installs skills into ~/.claude/
                             # (rules are skipped here with a warning — see step 2)

cd ~/your-project
~/path/to/agent-templates/install.sh   # installs rules into this project's .claude/rules/
                                       # (skills are already global, idempotent)

./uninstall.sh                         # remove everything (restores backups)
```

Re-run `./install.sh` to reinstall (picks up local changes). To sync with upstream: `git pull && ./install.sh`.

For interactive component picking, dry-runs, or installing into a specific project, see [Advanced: `at` CLI](#advanced-at-cli) below.

## Using the Skills

### Prerequisites

| Tool | Required by | Install (macOS) | Install (Debian/Ubuntu) |
|------|-------------|-----------------|--------------------------|
| `git` ≥ 2.5 | `make-pr`, `pr-babysit`, `latest-rebase` | `brew install git` | `apt install git` |
| `jq` | Installer (`at`) and several skills | `brew install jq` | `apt install jq` |
| `gh` | `make-pr`, `pr-babysit` | `brew install gh` | `apt install gh` |
| `uv` | `scripts/` (agent return-schema checks) | `brew install uv` | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
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
| **make-pr** | `/make-pr` | Drive a scoped task to done via a per-behavior TDD loop (tdd-runner + worker-coder), run gates, then review/critic. Best for high-risk work |
| **make-pr-lite** | `/make-pr-lite` | Lighter, cheaper sibling of make-pr for low-risk/greenfield PRs: one self-TDD coder + gates + a parallel review panel. Trades the live per-behavior RED witness for a test-form review lens |
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

## Language Rules

Opinionated coding standards that load automatically when editing matching files — per-language conventions plus two cross-cutting rules (design and TDD).

| Language | File | Target | Highlights |
|----------|------|--------|------------|
| Python | `rules/python.md` | Python 3.12+ | Type hints everywhere, `\|` union syntax, `match`/`case`, no bare `except` |
| TypeScript | `rules/typescript.md` | TypeScript 5.8+ | Strict mode, discriminated unions, `satisfies`, Zod validation |
| Rust | `rules/rust.md` | Edition 2024 | `?` propagation, `impl Trait` params, builder pattern, `#[must_use]` |
| C++ | `rules/cpp.md` | C++20 | Concepts, ranges, `std::format`, smart pointers, RAII |

### Cross-cutting rules

Two language-agnostic rules install alongside the language rules and load on broader globs:

| Rule | File | Loads on | Covers |
|------|------|----------|--------|
| Design principles | `rules/design-principles.md` | any source file | deep modules, information hiding, naming, complexity (Ousterhout) |
| TDD | `rules/tdd.md` | test files | red→green→refactor, vertical slices, public-interface tests |

### Installation

Rules are installed per-project into `.claude/rules/` by `./install.sh`. Each `rules/*.md` file is copied to `<project>/.claude/rules/`, where Claude Code picks them up automatically based on the file type being edited.

## Templates

### Project CLAUDE.md (`templates/CLAUDE.md.template`)

A starter `CLAUDE.md` for new projects — fill in the project name, tech stack, commands, and structure. It documents the skill entry points (`/make-pr`, `/pr-make-till-merge`, the review skills, and the repo-upkeep skills) so Claude Code picks the right workflow. Copy it to your project root as `CLAUDE.md` and edit the placeholders. It is not installed by `./install.sh` — copy it manually.

## Advanced: `at` CLI

The two scripts above cover the common case. For anything more specific, use the `at` CLI directly:

- `./at install` — interactive component picker (rules / skills / everything)
- `./at install --all --dry-run` — preview a full install without writing
- `./at install --all --target=/path/to/project` — install into a specific project
- `./at uninstall` — restore backups recorded during install
- `./at status` — show installation dashboard (what's installed, where, and when)
- `./at --help` — full command reference

## Installation Details

| Component | Install Location | Scope |
|-----------|-----------------|-------|
| Language Rules | `<project>/.claude/rules/*.md` | Per-project |
| Skills | `~/.claude/skills/<skill-name>/` | Global (all projects) |

The installer creates timestamped backups (`.bak.<timestamp>`) of any file it overwrites and records them in `.claude/.install-backup-manifest`. Run `./uninstall.sh` to restore all backups.

## Validation

Validate all artifacts without installing anything:

```bash
./validate.sh             # Full validation (skills, rules, agent schemas)
./validate.sh --smoke     # Smoke test: install into a temp dir and verify
./validate.sh --skills    # Validate only skills
./validate.sh --rules     # Validate only rules
./validate.sh --v1        # Validate agent return schemas + prompt shapes
```

Validation checks include:
- Every skill has a `SKILL.md` with valid YAML frontmatter (`name` and `description` fields)
- Every rule is a non-empty `.md` file
- Agent prompts match their declared return schemas
- Smoke test runs the full installer into a temp dir and verifies the expected files land

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes. If adding a new skill, include a `SKILL.md` with valid YAML frontmatter.
3. Run `./validate.sh` to ensure all checks pass.
4. Run `./validate.sh --smoke` to verify the installer still works end-to-end.
5. Open a pull request with a clear description of the change.

### Authoring a new skill

1. Copy `skills/latest-rebase/` as the minimal template — it has a single `SKILL.md` with the right frontmatter shape and no supporting files.
2. `SKILL.md` frontmatter requires two keys: `name` and `description`. The description **must** start with the literal string `"Use when"` — the validator fails otherwise (see `validate_skills` in `at`).
3. Fill in the skill body below the frontmatter. Claude Code loads the body when the user types `/your-skill-name`.
4. Run `./validate.sh --skills` to check the frontmatter, then `./validate.sh --smoke` to dry-run the installer end-to-end.

### Authoring a rule

Rules are per-project coding standards that load on matching file edits.

1. Create `rules/<language>.md`.
2. Frontmatter must include `paths:` as a **comma-separated quoted string** — not a YAML array. Example: `paths: "*.py, *.pyi"`. The validator rejects the `[...]` array form.
3. Run `./validate.sh --rules`.

## License

MIT -- see [LICENSE](LICENSE).
