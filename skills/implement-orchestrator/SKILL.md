---
name: implement-orchestrator
description: Use when the user asks to implement a plan using the agentic workflow, or invokes /implement-orchestrator, or says "implement this plan" or "execute this plan with agents". Works with any plan — from a plan.md file, conversation context, or user-provided description.
---

# Implement Orchestrator

Master orchestrator for the step-by-step agentic implementation pipeline. Breaks a plan into individual steps, implements each step separately with quality review via the `simplify` skill, and commits each step independently. Manages state via a temporary directory outside the repo.

```
Plan (from any source) --> Extract Steps --> For each step:
  [Plan Step] --> [Implement] --> [Run simplify skill] --> [Commit]
```

## Accepting the Plan

The plan can come from **any source** — do NOT require a `plan.md` file:

1. **Conversation context** — the user described the plan in the current conversation
2. **plan.md file** — if one exists in the working directory, use it
3. **Any other file** — the user may point to a design doc, issue, or spec

Extract the plan from whatever source is available. If no plan is clear, ask the user to describe what they want implemented.

## Worktree Isolation Policy

This orchestrator and its sub-skills **do not pass `isolation: "worktree"`** to the Agent
tool. Parallel agents write to naturally disjoint paths (source vs. test files), so
worktree isolation adds no safety — only cost.

Per the Agent tool contract: when `isolation: "worktree"` is used AND the agent makes file
changes, the harness leaves the worktree at `.claude/worktrees/agent-<hash>/` (~full repo
checkout, often gigabytes) for the caller to clean up. A prior incident accumulated 175 GB
of stale worktrees across 18 runs and filled the user's disk.

If a future change introduces `isolation: "worktree"` to any Agent call dispatched from
this pipeline, that change **must** invoke `/cleanup-worktrees` as its final step (even
on the error path) to remove the spawned worktree. See the final "Cleanup" section below.

## Temporary Directory Setup

All temporary artifacts are stored outside the repository to keep the workspace clean:

```bash
REPO_NAME=$(basename "$(git rev-parse --show-toplevel)")
BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD | tr '/' '-')
IMPL_TMP="${TMPDIR:-/tmp}/claude-impl/${REPO_NAME}/${BRANCH_NAME}"
mkdir -p "$IMPL_TMP"
```

All agents must resolve `IMPL_TMP` at the start and pass it to subagents. Every reference to temporary files below uses `$IMPL_TMP/` as the prefix.

## Step 1: Extract Implementation Steps

Parse the plan into discrete, independently implementable steps. Each step should be:
- Small enough to be a single coherent commit
- Self-contained (compiles/passes after the step is done)
- Ordered by dependency (earlier steps don't depend on later ones)

Write the extracted steps to `$IMPL_TMP/steps.md` for reference:
```markdown
## Step 1: [description]
[Details of what to implement]

## Step 2: [description]
[Details of what to implement]

...
```

## Step 2: Implement Each Step Separately

For **each step** in the plan, execute this cycle:

### 2a. Plan the Step

Dispatch a subagent to analyze the codebase and plan the specific step:
- Scan the codebase for reuse opportunities and existing patterns
- Apply clean-code principles (DRY, SRP, dependency direction)
- Produce a focused implementation plan for just this step

**REQUIRED SUB-SKILL:** clean-code-planner

### 2b. Data-Flow Trace

**Before writing any code**, check if this step modifies a type (dataclass, Pydantic model, Protocol, TypedDict, interface, struct). If it does:

1. Grep all imports of the type being modified:
   ```bash
   grep -rn "from.*import.*TypeName\|import.*TypeName" --include="*.py" --include="*.ts" .
   ```
2. Grep all attribute accesses of fields being changed:
   ```bash
   grep -rn "\.field_name" --include="*.py" --include="*.ts" .
   ```
3. List all consumer files and verify each will be updated in this step or a later step
4. If any consumer would break and is NOT covered by a later step, expand this step to include the fix

Skip this step if no types are being modified.

### 2c. Implement the Step

Implement the code changes for this step:
- Write source files and test files as needed
- Follow existing project conventions and language rules
- Run linter/formatter if available
- Run tests to verify the step works

**REQUIRED SUB-SKILL:** plan-codebase (for codebase analysis)

### 2d. Run the Simplify Skill

After implementation, **always** run the `simplify` skill on the changes from this step. This reviews the changed code for:
- Reuse opportunities
- Code quality issues
- Efficiency improvements

Apply any fixes the simplify skill identifies before committing.

**REQUIRED SKILL:** simplify

### 2e. Commit the Step

Create a single commit for this step with a descriptive message:
```
<type>: <description of what this step accomplishes>
```

The commit should include all source and test changes from this step, including any fixes from the simplify skill review.

### 2f. Move to Next Step

Repeat 2a-2e for the next step. Each step builds on the committed state of previous steps.

## State Management

All state lives in `$IMPL_TMP/` (outside the repository):
```
${TMPDIR}/claude-impl/<repo>/<branch>/
  steps.md              # Extracted plan steps
  current-step.md       # Current step being implemented (for recovery)
  manifest.json         # Step tracking and progress
```

`manifest.json` schema:
```json
{
  "total_steps": 3,
  "current_step": 2,
  "completed_steps": [
    {"step": 1, "description": "...", "commit": "<sha>", "files": ["..."]},
    {"step": 2, "description": "...", "commit": "<sha>", "files": ["..."]}
  ],
  "status": "in_progress",
  "timestamp": "<ISO-8601>"
}
```

Agents write to unique files -- no merge conflicts. Orchestrator context stays lean: read summaries, not full artifacts.

## Cleanup

After the pipeline completes — **including when it fails partway** — run both cleanup
steps. They are mandatory, not best-effort.

### Cleanup 1: Remove temporary directory

```bash
rm -rf "$IMPL_TMP"
```

This ensures no temporary planning artifacts persist after implementation is finished. If
you need to inspect artifacts after completion, they can be re-generated by re-running the
relevant phase.

### Cleanup 2: Remove any agent worktrees

Invoke the `cleanup-worktrees` skill to remove stale `.claude/worktrees/agent-*/` entries
created by isolation-worktree subagents (see "Worktree Isolation Policy" above). With the
current design this is a no-op, but it is load-bearing once any step here adopts
`isolation: "worktree"`, and it also catches worktrees left behind by previous interrupted
runs.

**REQUIRED SKILL:** cleanup-worktrees

Do not pass `--force` — the skill's uncommitted-changes guard preserves in-flight work
from other active sessions.

## Error Recovery

2-tier strategy:
1. **Retry** — if implementation or simplify fails for a step, retry that step (max 2 retries)
2. **Checkpoint** — each committed step is a natural checkpoint; on failure, the previously committed steps are safe

## Example Walkthrough

Given a plan with 3 steps:

1. **Step 1: Add user model** → implement → simplify → commit `feat: add user model with validation`
2. **Step 2: Add user API endpoints** → implement → simplify → commit `feat: add user CRUD API endpoints`
3. **Step 3: Add user authentication** → implement → simplify → commit `feat: add JWT-based user authentication`

Result: 3 clean, focused commits, each independently reviewed for quality.

## Quick Reference

| Phase | Action | Output |
|-------|--------|--------|
| Accept plan | Read from context, file, or conversation | Plan text |
| Extract steps | Break plan into ordered steps | `$IMPL_TMP/steps.md` |
| Per step: Plan | Analyze codebase for this step | Implementation approach |
| Per step: Data-flow trace | Grep consumers of modified types | Consumer file list |
| Per step: Implement | Write code and tests | Source + test files |
| Per step: Simplify | Run simplify skill | Quality-reviewed code |
| Per step: Commit | Commit all changes | One focused commit |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Requiring plan.md to exist | Accept plan from any source — conversation, file, or description |
| Implementing all steps at once | Implement one step at a time, commit after each |
| Skipping simplify skill | ALWAYS run simplify after every implementation step |
| Batching commits | One commit per step, not one commit for everything |
| Steps that depend on later steps | Order steps by dependency — earlier steps are independent |
| Huge steps | Break into smaller, independently committable units |
| Storing temp files in repo | Use `$IMPL_TMP` (outside repo) for all temporary artifacts |
| Modifying a type without checking consumers | ALWAYS run data-flow trace (step 2b) when changing types — grep imports and attribute accesses |
