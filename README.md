# agent-templates

A shareable collection of Claude Code skills, hooks, language rules, and templates -- centered around a multi-phase agentic implementation workflow.

## Getting Started

```bash
git clone https://github.com/anthropics/agent-templates.git
cd agent-templates
./install.sh      # install everything (rules + skills + hooks)
./uninstall.sh    # remove everything (restores backups)
```

Re-run `./install.sh` to reinstall (picks up local changes). To sync with upstream: `git pull && ./install.sh`.

For interactive component picking, dry-runs, or installing into a specific project, see [Advanced: `at` CLI](#advanced-at-cli) below.

## Using the Skills

### Prerequisites

- `gh` CLI authenticated (`gh auth login`) with `repo` scope; for project linking via `/make-pr` and `/issue-make`, also run `gh auth refresh -s read:project,project`
- `jq` installed
- Claude Code CLI installed
- Verify the install with `./validate.sh`

### Mental model

A skill is a named procedure invoked by typing `/skill-name` in a Claude Code session. Some skills are aliases that dispatch to another skill with identical arguments -- for example, `/pr-make` dispatches to `/make-pr`, and `/plan-code` dispatches to `/clean-code-planner`. The Agentic Workflow diagram below shows how `/implement-orchestrator` chains lower-level skills together.

### Your first run

Try the lowest-risk skill to verify everything works:

```
/wt-create scratch
```

This creates a sibling worktree at `../<repo>-scratch/`, a branch `scratch`, and prints the `cd` / `tmux` commands to enter it.

Clean up when done:

```bash
git worktree remove ../<repo>-scratch
git branch -D scratch
```

### Decision tree -- "I have X, I want Y"

| What you have | What you want | Skill |
|---|---|---|
| An idea | A merged PR | `/plan-till-merge` |
| A `plan.md` file | A merged PR | `/implement-till-merge` |
| A finished branch (committed work) | A merged PR | `/pr-make-till-merge` |
| An open PR | A merged PR | `/pr-babysit` |

### Other daily tasks

- Sync main: `/latest-update`
- Rebase onto main: `/latest-rebase`
- Review the current diff: `/review-and-fix` or `/multi-review`
- Open a GitHub issue: `/issue-make`
- Create a worktree for parallel work: `/wt-create`
- Remove stale agent-generated worktrees (under `.claude/worktrees/agent-*/`): `/cleanup-worktrees`

## Components Overview

| Component | Location | Description |
|-----------|----------|-------------|
| **Skills** | `skills/` | Agentic workflow pipeline -- orchestration, planning, implementation, and review |
| **Language Rules** | `rules/` | Opinionated coding standards for Python, TypeScript, Rust, and C++ |
| **Hooks** | `hooks/` | Automation scripts for Slack notifications and permission auto-approval |
| **Templates** | `templates/` | Starter CLAUDE.md and settings.json for new projects |

## Agentic Workflow

The core of this repository is a step-by-step agentic implementation pipeline. Provide a plan from any source (conversation, file, or description) and invoke `/implement-orchestrator` to run the full pipeline:

```
Plan (any source) ──> implement-orchestrator
                            │
                     Extract Steps
                            │
                     For each step:
                     ┌──────┴──────┐
                     ▼              ▼
               Impl Coder    Test Coder              Implement
                     │              │
                     └──────┬──────┘
                            ▼
                     Run simplify skill               Quality Review
                            │
                            ▼
                     Commit step                      One commit per step
                            │
                     Next step ──> repeat
```

Each plan step produces one focused commit, independently reviewed for quality via the `simplify` skill. A 3-step plan produces 3 commits.

### Skills Reference

Organized by who invokes the skill. Skills in the first two groups are meant to be typed directly; skills in the third group are called internally by the orchestrator.

#### End-to-end pipelines

Top-level skills that run full workflows by composing lower-level skills.

| Skill | Command | Purpose |
|-------|---------|---------|
| **plan-till-merge** | `/plan-till-merge` | Plan -> implement -> PR -> babysit. Composes: clean-code-planner -> implement-orchestrator -> issue-make -> make-pr -> pr-babysit |
| **implement-till-merge** | `/implement-till-merge` | Implement a plan -> PR -> babysit -> cleanup. Composes: implement-orchestrator -> pr-make-till-merge -> cleanup-worktrees |
| **pr-make-till-merge** | `/pr-make-till-merge` | Create PR from current branch -> babysit. Composes: make-pr -> pr-babysit |

#### Building blocks -- you invoke directly

| Skill | Command | Purpose |
|-------|---------|---------|
| **plan-arch** | `/plan-arch` | Architecture design doc for a chosen approach |
| **plan-options** | `/plan-options` | Evaluate multiple approaches with tradeoffs |
| **clean-code-planner** | `/clean-code-planner` | Produce a code plan before any code change |
| **implement-orchestrator** | `/implement-orchestrator` | Step-by-step agentic implementation from a plan |
| **make-pr** | `/make-pr` | Run gates, review, push, create PR |
| **pr-babysit** | `/pr-babysit` | Poll PR until ready to merge, fix review/CI issues |
| **review-and-fix** | `/review-and-fix` | Review current diff, fix CRITICAL and MAJOR issues |
| **multi-review** | `/multi-review` | Multi-model code review via external AI CLIs |
| **issue-make** | `/issue-make` | Create or update a GitHub issue with planning artifacts |
| **wt-create** | `/wt-create` | Create a git worktree for parallel work |
| **cleanup-worktrees** | `/cleanup-worktrees` | Remove stale agent-generated worktrees under `.claude/worktrees/agent-*/` |
| **latest-update** | `/latest-update` | Pull main, clean up merged branches, validate, install |
| **latest-rebase** | `/latest-rebase` | Rebase current branch onto latest main |
| **python-coding-rules** | `/python-coding-rules` | Apply Python 3.12+ coding standards (TypeScript / Rust / C++ rules load automatically via `rules/` when editing matching files) |

#### Dispatched internally -- don't invoke directly

These skills are internal sub-components for orchestrator pipelines. Most users shouldn't invoke them directly.

| Skill | Purpose |
|-------|---------|
| **plan-codebase** | Analyze codebase, produce implementation spec for a step |
| **plan-tests** | Discover test patterns, produce test plan for a step |
| **implement-parallel** | Dispatch parallel Impl Coder and Test Coder for a step |
| **review-parallel** | Run parallel reviewers with severity-based consensus |

**Aliases** (same arguments, alternate slash name): `/plan-code` -> `/clean-code-planner`, `/pr-make` -> `/make-pr`.

## Language Rules

Opinionated, per-language coding standards that load automatically when editing matching files.

| Language | File | Target | Highlights |
|----------|------|--------|------------|
| Python | `rules/python.md` | Python 3.12+ | Type hints everywhere, `\|` union syntax, `match`/`case`, no bare `except` |
| TypeScript | `rules/typescript.md` | TypeScript 5.8+ | Strict mode, discriminated unions, `satisfies`, Zod validation |
| Rust | `rules/rust.md` | Edition 2024 | `?` propagation, `impl Trait` params, builder pattern, `#[must_use]` |
| C++ | `rules/cpp.md` | C++20 | Concepts, ranges, `std::format`, smart pointers, RAII |

### Installation

Rules are installed per-project into `.claude/rules/` by `./install.sh`. Each `rules/*.md` file is copied to `<project>/.claude/rules/`, where Claude Code picks them up automatically based on the file type being edited.

## Hooks

### Slack Notification Hook (`hooks/notify-slack.sh`)

Sends a Slack message when Claude Code needs input (`Notification`) or finishes a task (`Stop`). Messages include the user's original task, notification context, repo name, and branch. Silently no-ops if no Slack credentials are set. Never blocks Claude -- always exits 0.

Two modes are supported:

| Mode | Variables | Threading | Message Updates |
|------|-----------|-----------|-----------------|
| **Webhook** (simple) | `CLAUDE_SLACK_WEBHOOK_URL` | No | No |
| **Bot API** (recommended) | `CLAUDE_SLACK_BOT_TOKEN` + `CLAUDE_SLACK_CHANNEL` | Yes | Yes |

Bot API mode groups all events from the same Claude Code session into a single Slack thread. The parent message is updated with the final status when the task finishes.

#### Webhook Setup (simple)

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Name it (e.g. "Claude Code Notifications"), pick your workspace
3. Left sidebar: **Incoming Webhooks** → toggle **On**
4. Click **Add New Webhook to Workspace** → pick a channel
5. Copy the webhook URL and add to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export CLAUDE_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T.../B.../xxx"
```

6. Verify with `./validate.sh --hooks` — it will confirm the variable is set.

#### Bot API Setup (threading)

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → **From scratch**
2. Under **OAuth & Permissions**, add the `chat:write` scope
3. **Install to Workspace** → copy the **Bot User OAuth Token** (`xoxb-...`)
4. Invite the bot to your channel: `/invite @YourBotName`
5. Get the channel ID (right-click channel name → **View channel details** → copy ID)
6. Add to your shell profile:

```bash
export CLAUDE_SLACK_BOT_TOKEN="xoxb-..."
export CLAUDE_SLACK_CHANNEL="C0123456789"
```

Both modes can be configured simultaneously — bot API takes priority when available.

### Auto-Approve Hook (`hooks/auto-approve.sh`)

Runs on `PreToolUse` and auto-approves safe, read-only tools (Read, Glob, Grep, LS, WebSearch, WebFetch, NotebookRead). Reduces permission prompts during agentic runs. Fails open if `jq` is not installed.

### Installation

Hooks are installed globally to `~/.claude/hooks/` and registered in `~/.claude/settings.json` by `./install.sh`. The installer merges hook configuration from `templates/settings-hooks.json` into your existing `settings.json` using `jq`. If `jq` is not available, it prints the JSON for manual merging.

## Templates

### Settings Hook Template (`templates/settings-hooks.json`)

Pre-configured `settings.json` fragment that registers the Slack notification and auto-approve hooks on the correct event types (`Notification`, `Stop`, `PreToolUse`). The settings template is merged automatically when installing hooks.

## Advanced: `at` CLI

The two scripts above cover the common case. For anything more specific, use the `at` CLI directly:

- `./at install` — interactive component picker (rules / skills / hooks / everything)
- `./at install --all --dry-run` — preview a full install without writing
- `./at install --all --target=/path/to/project` — install into a specific project
- `./at status` — show installation dashboard (what's installed, where, and when)
- `./at update --all` — pull latest and reinstall tracked components
- `./at --help` — full command reference

## Installation Details

| Component | Install Location | Scope |
|-----------|-----------------|-------|
| Language Rules | `<project>/.claude/rules/*.md` | Per-project |
| Skills | `~/.claude/skills/<skill-name>/` | Global (all projects) |
| Hooks | `~/.claude/hooks/*.sh` | Global (all projects) |
| Settings | `~/.claude/settings.json` | Global (all projects) |

The installer creates timestamped backups (`.bak.<timestamp>`) of any file it overwrites and records them in `.claude/.install-backup-manifest`. Run `./uninstall.sh` to restore all backups.

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
