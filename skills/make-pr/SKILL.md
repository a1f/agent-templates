---
name: make-pr
description: Use when the user wants to create or update a pull request from the current branch, or invokes /make-pr. Runs repository gates, fixes errors, performs a quick review, and manages the full PR lifecycle on GitHub.
---

# Make PR

Create or update a GitHub pull request from the current branch. Bootstraps gate definitions from the repo's existing CI, runs gates in a fix loop, performs a quick review, then creates or updates the PR with issue linking and reviewer assignment.

```
Current branch with commits
  --> Phase 0: Discovery (base branch, existing PR, issue, reviewers)
  --> Phase 0.5: Gate Bootstrap (resolve gates from gates.json / CI / language detection)
  --> Phase 1: Gate Loop (run gates in order, fix errors, max 5 iterations)
  --> Phase 1.5: Simplify (reuse, quality, efficiency review via /simplify)
  --> Phase 2: Quick Review (single-pass diff review, fix CRITICAL/MAJOR, max 2 iters)
  --> Phase 2.5: Review and Fix (deeper review via /review-and-fix)
  --> Phase 2.7: Agent Review (comprehensive specialized-agent review via /pr-review-toolkit:review-pr)
  --> Phase 3: Push + PR Lifecycle (create or update PR, link issue, assign reviewers)
```

## Prerequisites

The `gh` CLI must be authenticated with the following token scopes:
- `repo` — read/write access to repository
- `read:project` — list projects linked to the repo
- `project` — add issues to projects

If project scopes are missing, run:
```bash
gh auth refresh -s read:project,project
```

The skill will still work without project scopes — it just skips the project linking step and warns the user.

## Arguments

Parse arguments from the user's message. All are optional:

| Arg | Default | Example |
|-----|---------|---------|
| `--issue=N` | Auto-detect or auto-create | `--issue=42` |
| `--reviewers=user1,user2` | Inferred from recent commit authors | `--reviewers=alice,bob` |
| `--title="..."` | Generated from commits | `--title="Add user auth"` |
| `--base=branch` | Repository default branch | `--base=develop` |
| `--draft` | Not draft | `--draft` |
| `--no-agent-review` | Agent review enabled | `--no-agent-review` |

## Phase 0: Discovery

Run all of these in parallel at the start:

### 0a. Branch and Diff Info

```bash
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
BASE_BRANCH="${ARG_BASE:-$(gh repo view --json defaultBranchRef -q '.defaultBranchRef.name')}"
```

Verify the current branch is NOT the base branch. If it is, stop and tell the user to create a feature branch first.

Verify there are commits ahead of base:
```bash
git log "${BASE_BRANCH}..HEAD" --oneline
```
If no commits, stop and tell the user there is nothing to PR.

### 0b. Existing PR Check

```bash
gh pr list --head "$CURRENT_BRANCH" --json number,title,url,state --jq '.[0]'
```

If a PR exists, store its number for Phase 3 (update instead of create).

### 0c. Issue Detection

Issue detection and creation is handled by `/issue-make`. Pass `--issue=N` if the user provided one; otherwise `/issue-make` will auto-detect from the branch name or commit messages, or create a new issue.

### 0d. Reviewer Detection

If `--reviewers` is provided, use those. Otherwise, infer from recent commit history:

```bash
# Get unique authors from last 50 commits on base branch, excluding the current user
CURRENT_USER=$(gh api user -q '.login')
gh api "repos/{owner}/{repo}/commits?sha=${BASE_BRANCH}&per_page=50" \
  -q '.[].author.login' | sort | uniq -c | sort -rn | head -5
```

Pick the top 2 contributors (excluding the current user) as default reviewers. If no contributors found, leave reviewers empty and warn the user.

## Phase 0.5: Gate Bootstrap

Resolve what gates to run. Three sources, tried in priority order:

### Source 1: `.claude/gates.json` (explicit, highest priority)

If `.claude/gates.json` exists, use it directly. This is the deterministic path — no guessing.

Schema:
```json
{
  "setup": "uv sync --frozen",
  "gates": [
    { "name": "format",    "run": "ruff format --check .", "fix": "ruff format ." },
    { "name": "lint",      "run": "ruff check .",          "fix": "ruff check --fix ." },
    { "name": "typecheck", "run": "pyright" },
    { "name": "test",      "run": "pytest -x" }
  ]
}
```

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `setup` | string | no | Command to install dependencies before gates run |
| `gates` | array | yes | Ordered list of gates |
| `gates[].name` | string | yes | Gate identifier (used in commit messages) |
| `gates[].run` | string | yes | Check command. Exit 0 = pass. |
| `gates[].fix` | string | no | Auto-fix command. Run before `run` if gate fails. |
| `gates[].required` | bool | no | Default `true`. If `false`, failure is a warning, not a blocker. |

Array order IS execution order.

### Source 2: Existing CI workflow (parse from repo)

If no `gates.json`, look for the repo's CI configuration:

```
Search order:
1. .github/workflows/ci.yml
2. .github/workflows/ci.yaml
3. .github/workflows/test.yml
4. .github/workflows/test.yaml
5. .github/workflows/checks.yml
6. .github/workflows/*.yml (any workflow triggered on pull_request or push)
```

Read the workflow YAML and extract gate commands from `run:` steps. Map them to gates:

**Pattern matching for extraction:**

| If `run:` contains | Gate name | Fix command |
|---------------------|-----------|-------------|
| `ruff format --check` or `ruff format` with `--check` | format | `ruff format .` |
| `cargo fmt -- --check` | format | `cargo fmt` |
| `biome format` or `prettier --check` | format | `biome format --write .` / `prettier --write .` |
| `ruff check` | lint | `ruff check --fix .` |
| `cargo clippy` | lint | (none — clippy has no auto-fix) |
| `biome check` or `eslint` | lint | `biome check --fix .` / `eslint --fix .` |
| `pyright` or `mypy` | typecheck | (none) |
| `tsc --noEmit` or `tsc -noEmit` | typecheck | (none) |
| `cargo check` | typecheck | (none) |
| `pytest` | test | (none) |
| `cargo nextest` or `cargo test` | test | (none) |
| `vitest run` or `jest` | test | (none) |
| `cargo build` or `uv build` or `npm run build` | build | (none) |

Also extract the setup step — look for commands like `uv sync`, `pnpm install`, `cargo build`, `npm ci` in earlier steps of the same job.

**Generate `.claude/gates.json` from the extracted commands** and commit it:
```
chore: add .claude/gates.json from CI config
```

This ensures the next run is deterministic (Source 1).

**Validation:** After generating `gates.json`, verify it covers all gate categories present in CI. Check for each category: format, lint, typecheck, test, build. If CI has a pyright/mypy/tsc step but the extracted gates lack a `typecheck` gate, warn: "CI has typecheck but gates.json does not — add it." Same for test, build, etc. Do NOT generate a gates.json that is missing categories the CI actually checks.

### Source 3: Language detection (last resort)

If no CI workflow exists, detect the project language and generate gates from templates:

| File exists | Language | Template |
|-------------|----------|----------|
| `pyproject.toml` | Python | `gates/python.json` |
| `Cargo.toml` | Rust | `gates/rust.json` |
| `package.json` | TypeScript/JS | `gates/typescript.json` |
| `CMakeLists.txt` | C++ | `gates/cpp.json` |

Read the template from this skill's `gates/` directory. Adapt it based on what's actually in the config file (e.g., if `pyproject.toml` has `[tool.mypy]` instead of pyright, use mypy).

Generate `.claude/gates.json` and commit it.

### Gate Validation

After resolving gates from any source, validate them before entering the fix loop:

1. **Run `setup` command** if present
   - If it fails with "command not found" (e.g., `uv: command not found`):
     → Stop and tell the user exactly what to install
   - If it fails with missing lockfile (e.g., `No lockfile found`):
     → Try generating it (`uv lock`, `pnpm install`) then re-run setup
   - If it fails with other errors:
     → Stop and show the error

2. **For each gate, check if the command is available:**
   ```bash
   command -v "$(echo "$GATE_RUN" | awk '{print $1}')" >/dev/null 2>&1
   ```
   - If not found, check if it's a dev dependency that can be installed:
     - Python: `uv add --dev <tool>` then re-run setup
     - Node: `pnpm add -D <tool>` then re-run setup
     - Rust: usually available via cargo, no action needed
   - If still not found after install attempt:
     → Remove this gate from the run, warn the user
   - If the gate is `required: true` and can't be made runnable:
     → Stop and tell the user what's missing

3. **Proceed with validated gates only**

## Phase 1: Gate Loop

Run gates in the order defined by `gates.json`. This order matters — earlier gates (format, lint) fix issues that would cause later gates (typecheck, test) to fail.

**Max 5 iterations total** across all gates.

For each gate:

1. Run the `run` command
2. If it passes (exit 0), move to the next gate
3. If it fails:
   a. If `fix` command exists, run it first
   b. Run `run` command again
   c. If errors remain, read the error output and fix manually using `gate-runner-prompt.md`
   d. After fixing, restart from the first gate — fixes may introduce new issues
   e. Stage and commit fixes: `fix: resolve {gate_name} errors`

**Important:**
- Parse error output carefully. Focus on the specific files and line numbers reported.
- Do NOT blindly retry — if the same error appears twice, analyze it differently.
- If a gate has no `fix` command, go straight to manual fix.
- If a gate has `required: false` and fails, log a warning and continue to the next gate.

**Exit conditions:**
- All required gates pass → proceed to Phase 2
- 5 iterations reached with remaining failures → warn the user with the list of unresolved errors, ask whether to proceed with PR anyway

## Phase 1.5: Simplify

Before reviewing, run `/simplify` on the changes. Use the Skill tool to invoke `simplify`. This reviews the changed code for reuse opportunities, code quality issues, and efficiency improvements. If `/simplify` makes changes, commit them and re-run gates (Phase 1) with max 2 more iterations.

## Phase 2: Quick Review

A lighter alternative to `/review-parallel`. Single-pass review focused on the diff.

### 2a. Review the Diff

Review `git diff ${BASE_BRANCH}...HEAD` yourself (no subagent needed). Focus on:

- **CRITICAL:** Security vulnerabilities, crashes, data corruption
- **MAJOR:** Logic errors, spec violations, race conditions

Do NOT flag: style nits, minor naming, LOW-severity items. The gates already handle formatting and linting.

### 2b. Fix Issues

If CRITICAL or MAJOR issues found:
1. Fix them
2. Commit: `fix: resolve review issues`
3. Re-run gates (Phase 1) — but only 2 more iterations max
4. Re-review the new diff only (not the full diff again)

**Max 2 review iterations.** If issues remain after 2 passes, list them in the PR body as known issues.

## Phase 2.5: Review and Fix

After the quick review, invoke `/review-and-fix` for a deeper pass. Use the Skill tool to invoke `review-and-fix` with `--base=$BASE_BRANCH`. This catches issues the quick review may have missed. If `/review-and-fix` makes changes, it commits them — re-run gates (Phase 1) with max 2 more iterations before proceeding.

## Phase 2.7: Agent Review

Run the comprehensive multi-agent review via the `pr-review-toolkit` plugin. Use the Skill tool to invoke `pr-review-toolkit:review-pr` with argument `all parallel` so all applicable specialized agents run concurrently.

The toolkit auto-selects agents based on what changed in the diff:

- **code-reviewer** — general quality and CLAUDE.md compliance (always)
- **pr-test-analyzer** — behavioral test coverage (if test files changed)
- **silent-failure-hunter** — error handling and fallback logic (if error paths changed)
- **comment-analyzer** — comment accuracy (if comments/docs added)
- **type-design-analyzer** — type encapsulation and invariants (if new types added)

### 2.7a. Apply Findings

The toolkit returns an aggregated report with findings bucketed by severity. Treat them as follows:

| Toolkit severity | Action |
|------------------|--------|
| **Critical Issues** | Fix immediately |
| **Important Issues** | Fix immediately |
| **Suggestions** | Skip — not blocking for PR creation |

Read each referenced file at the flagged `file:line`, understand context, then apply the fix. Don't blindly apply — if a finding is a false positive, note it in the PR body instead of fixing.

### 2.7b. Commit and Re-gate

If fixes were applied:

1. Stage only the files modified by fixes
2. Commit: `fix: address agent review findings — <summary>`
3. Re-run gates (Phase 1) with max 2 more iterations

**Max 2 iterations of Phase 2.7.** If Critical/Important issues persist after 2 passes, list them in the PR body under a `## Known Issues` section and proceed to Phase 3.

### 2.7c. Skip Conditions

Skip Phase 2.7 if any of the following hold (record the reason in the final output):

- Diff is under 20 lines changed — the earlier phases already cover it
- `.claude/gates.json` has `"skip_agent_review": true`
- User passed `--no-agent-review` flag

## Phase 3: PR Lifecycle

### 3a. Debug Marker Scan

Before pushing, scan changed files for debug markers:

```bash
git diff "${BASE_BRANCH}...HEAD" --name-only | xargs grep -nE '(DEBUG|HACK|FIXME|XXX|console\.log\(|print\(.*debug|breakpoint\(\))' 2>/dev/null
```

If any markers are found, show them to the user and ask whether to remove them before pushing. Do NOT silently push code with debug markers.

Exclude: `TODO` comments that are genuine task markers (not debug leftovers), and test files where `print()` may be intentional.

### 3b. Push

```bash
git push -u origin "$CURRENT_BRANCH"
```

### 3c. Generate PR Content

Use `pr-body-prompt.md` to generate the title and body. Inputs:
- Issue description (if linked)
- `git log ${BASE_BRANCH}..HEAD --oneline`
- `git diff ${BASE_BRANCH}...HEAD --stat`
- List of gates that were run and passed

### 3d. Create or Update PR

**If no existing PR:**

```bash
gh pr create \
  --base "$BASE_BRANCH" \
  --title "$PR_TITLE" \
  --body "$PR_BODY" \
  --reviewer "$REVIEWERS" \
  ${DRAFT:+--draft}
```

**If PR already exists:**

```bash
gh pr edit "$PR_NUMBER" \
  --title "$PR_TITLE" \
  --body "$PR_BODY"

# Add a comment noting the update
gh pr comment "$PR_NUMBER" --body "$UPDATE_COMMENT"
```

### 3e. Issue Lifecycle (via `/issue-make`) — NOT OPTIONAL

**ALWAYS** invoke `issue-make` using the Skill tool. This is mandatory, not optional. Pass:
- `--issue=N` if detected in Phase 0c
- `--title` derived from the PR title (e.g., PR title "feat: add user auth" → issue title "Add user auth")
- Any `--project` argument the user passed to `/make-pr`

`/issue-make` handles: finding or creating the issue, linking to a project, and attaching planning `.md` files as a gist.

After `/issue-make` returns, include `Closes #N` in the PR body to link it. If updating an existing PR, ensure the issue link is in the updated body.

### 3g. Final Output

Print to the user:
- PR URL
- Issue URL
- Project linked (name, or "none")
- Reviewers assigned
- Gates that passed
- Any known issues from review

## State Management

Minimal state — this skill is designed to be stateless and idempotent. Running `/make-pr` again on the same branch simply re-runs gates, re-reviews, and updates the existing PR.

No temporary directory needed. All information comes from git, GitHub, and `.claude/gates.json`.

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Running on the base branch | Check and refuse early in Phase 0 |
| Creating duplicate PRs | Always check for existing PR first |
| Infinite gate loop | Hard cap at 5 iterations, then warn user |
| Fixing style in review | Gates handle style — review only catches logic/security issues |
| Force-pushing | Never force-push. Regular `git push` only. If push fails due to remote changes, pull and re-run gates |
| Committing unrelated files | Only stage files that were modified by gate fixes or review fixes |
| Generating gates.json that doesn't match CI | Parse CI commands exactly, don't guess. If unsure, include the command verbatim |
| Installing system packages | Never run sudo/apt/brew. Tell the user what to install |
| Suppressing lint errors with noqa/ignore | Fix the actual error. Only suppress genuine false positives with explanation |
| Extracting only format/lint gates from CI | Extract ALL gates — compare extracted categories against CI steps, warn if typecheck/test are missing |
| Skipping /issue-make | ALWAYS run /issue-make in Phase 3d — it ensures issue exists with planning artifacts |
| Pushing before review completes | Phase 2 (Quick Review) MUST finish before Phase 3 (Push). Never skip review. |
| Fixing Suggestions from agent review | Phase 2.7 fixes only Critical/Important. Suggestions go in the PR body or are skipped entirely. |
| Looping Phase 2.7 until every finding is gone | Cap at 2 iterations. Persistent Critical/Important findings go under `## Known Issues` in the PR body. |
| Running agent review on trivial diffs | Skip Phase 2.7 when the diff is under 20 lines — earlier phases already cover it. |
