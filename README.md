# agent-templates

A shareable collection of Claude Code skills, hooks, language rules, and templates -- centered around a multi-phase agentic implementation workflow.

## Quick Start

```bash
git clone https://github.com/anthropics/agent-templates.git
cd agent-templates
./install.sh          # Interactive: pick components to install
```

Or install everything non-interactively:

```bash
./install.sh --non-interactive --all
./install.sh --target=/path/to/project --all   # Install to a specific project
./install.sh --dry-run --all                   # Preview without changes
./install.sh --uninstall                       # Restore from backups
```

## Components Overview

| Component | Location | Description |
|-----------|----------|-------------|
| **Skills** | `skills/` | Agentic workflow pipeline -- orchestration, planning, implementation, and review |
| **Language Rules** | `rules/` | Opinionated coding standards for Python, TypeScript, Rust, and C++ |
| **Hooks** | `hooks/` | Automation scripts for Slack notifications and permission auto-approval |
| **Templates** | `templates/` | Starter CLAUDE.md and settings.json for new projects |

## Agentic Workflow

The core of this repository is a 4-phase agentic implementation pipeline. Start with an approved `plan.md` and invoke `/implement-orchestrator` to run the full pipeline:

```
Plan.md (approved) ──> implement-orchestrator
                            │
                     ┌──────┴──────┐
                     ▼              ▼
               Code Planner    Test Planner         Phase 1: Planning
                     │              │
                     └──────┬──────┘
                            ▼
                     code-spec.md + test-plan.md
                            │
                     ┌──────┴──────┐
                     ▼              ▼
               Test Coder     Impl Coder            Phase 2: Implementation
                            │
               ┌────────────┼────────────┐
               ▼            ▼            ▼
          Arch Review   DRY Review   Simplify        Phase 3: Refactoring
               ┌──┬──┬──┬──┼──┐
               ▼  ▼  ▼  ▼  ▼  ▼
         5 Code Reviewers (consensus)               Phase 4: Code Review
                            │
                       todo.md → Fix Loop (max 3x) → Done
```

### Skills Reference

| Skill | Command | Purpose |
|-------|---------|---------|
| **implement-orchestrator** | `/implement-orchestrator` | Run the full 4-phase pipeline from an approved plan |
| **plan-codebase** | `/plan-codebase` | Phase 1a: Analyze codebase and produce `code-spec.md` |
| **plan-tests** | `/plan-tests` | Phase 1b: Discover test patterns and produce `test-plan.md` |
| **implement-parallel** | `/implement-parallel` | Phase 2: Dispatch parallel Impl Coder and Test Coder agents |
| **review-parallel** | `/review-parallel` | Phases 3-4: Run parallel reviewers with severity-based consensus |
| **clean-code-planner** | `/clean-code-planner` | Produce a code plan before any code change (any size) |
| **python-coding-rules** | `/python-coding-rules` | Apply Python 3.12+ coding standards interactively |

## Language Rules

Opinionated, per-language coding standards that load automatically when editing matching files.

| Language | File | Target | Highlights |
|----------|------|--------|------------|
| Python | `rules/python.md` | Python 3.12+ | Type hints everywhere, `\|` union syntax, `match`/`case`, no bare `except` |
| TypeScript | `rules/typescript.md` | TypeScript 5.8+ | Strict mode, discriminated unions, `satisfies`, Zod validation |
| Rust | `rules/rust.md` | Edition 2024 | `?` propagation, `impl Trait` params, builder pattern, `#[must_use]` |
| C++ | `rules/cpp.md` | C++20 | Concepts, ranges, `std::format`, smart pointers, RAII |

### Installation

Rules are installed per-project into `.claude/rules/`:

```bash
./install.sh   # Select [1] Language Rules
```

This copies each `rules/*.md` file to `<project>/.claude/rules/`, where Claude Code picks them up automatically based on the file type being edited.

## Hooks

### Slack Notification Hook (`hooks/notify-slack.sh`)

Sends a Slack message when Claude Code fires a `Notification` or `Stop` event. Configure by setting the `CLAUDE_SLACK_WEBHOOK_URL` environment variable. Silently no-ops if the variable is unset. Never blocks Claude -- always exits 0.

### Auto-Approve Hook (`hooks/auto-approve.sh`)

Runs on `PreToolUse` and auto-approves safe, read-only tools (Read, Glob, Grep, LS, WebSearch, WebFetch, NotebookRead). Reduces permission prompts during agentic runs. Fails open if `jq` is not installed.

### Installation

Hooks are installed globally to `~/.claude/hooks/` and registered in `~/.claude/settings.json`:

```bash
./install.sh   # Select [3] Hooks
```

The installer merges hook configuration from `templates/settings-hooks.json` into your existing `settings.json` using `jq`. If `jq` is not available, it prints the JSON for manual merging.

## Templates

### CLAUDE.md Template (`templates/CLAUDE.md.template`)

A starter `CLAUDE.md` for new projects. Includes placeholders for project name, tech stack, build/test/lint commands, and a reference table of all skill entry points.

### Settings Hook Template (`templates/settings-hooks.json`)

Pre-configured `settings.json` fragment that registers the Slack notification and auto-approve hooks on the correct event types (`Notification`, `Stop`, `PreToolUse`).

### Installation

```bash
./install.sh   # Select [4] CLAUDE.md template
```

The CLAUDE.md template is installed to `<project>/CLAUDE.md`. The settings template is merged automatically when installing hooks.

## Installation Details

| Component | Install Location | Scope |
|-----------|-----------------|-------|
| Language Rules | `<project>/.claude/rules/*.md` | Per-project |
| Skills | `~/.claude/skills/<skill-name>/` | Global (all projects) |
| Hooks | `~/.claude/hooks/*.sh` | Global (all projects) |
| Settings | `~/.claude/settings.json` | Global (all projects) |
| CLAUDE.md | `<project>/CLAUDE.md` | Per-project |

The installer creates timestamped backups (`.bak.<timestamp>`) of any file it overwrites and records them in `.claude/.install-backup-manifest`. Run `./install.sh --uninstall` to restore all backups.

## Validation

Validate all artifacts without installing anything:

```bash
./validate.sh             # Full validation (skills, rules, hooks, settings template)
./validate.sh --smoke     # Smoke test: dry-run install + validate + uninstall
./validate.sh --skills    # Validate only skills
./validate.sh --rules     # Validate only rules
./validate.sh --hooks     # Validate only hooks
./validate.sh --settings  # Validate only settings template
```

Validation checks include:
- Every skill has a `SKILL.md` with valid YAML frontmatter (`name` and `description` fields)
- Every rule is a non-empty `.md` file
- Every hook is an executable `.sh` file with a valid shebang
- The settings template is valid JSON with a `hooks` key
- Smoke test runs the full installer in dry-run mode and verifies no errors

## Research Documents

Background research used during development. These documents are not installed anywhere -- they live in the repo for reference.

| Document | Path |
|----------|------|
| Agent Orchestration Patterns | `docs/research/agent-orchestration.md` |
| Code Review Automation | `docs/research/code-review-automation.md` |
| Claude Code Skills | `docs/research/claude-code-skills.md` |
| Claude Code Rules | `docs/research/claude-code-rules.md` |
| Claude Code Hooks | `docs/research/claude-code-hooks.md` |
| Claude Code Settings | `docs/research/claude-code-settings.md` |
| Python Best Practices | `docs/research/python-best-practices.md` |
| TypeScript Best Practices | `docs/research/typescript-best-practices.md` |
| Rust Best Practices | `docs/research/rust-best-practices.md` |
| C++ Best Practices | `docs/research/cpp-best-practices.md` |
| Slack Webhooks | `docs/research/slack-webhooks.md` |
| Installer Patterns | `docs/research/installer-patterns.md` |
| Validation Patterns | `docs/research/validation-patterns.md` |

## Contributing

1. Fork the repository and create a feature branch.
2. Make your changes. If adding a new skill, include a `SKILL.md` with valid YAML frontmatter.
3. Run `./validate.sh` to ensure all checks pass.
4. Run `./validate.sh --smoke` to verify the installer still works end-to-end.
5. Open a pull request with a clear description of the change.

## License

MIT -- see [LICENSE](LICENSE).
