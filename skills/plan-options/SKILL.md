---
name: plan-options
description: Use when the user needs to evaluate multiple approaches to a complex change, or invokes /plan-options. Generates options with tradeoff analysis and a recommendation.
---

# Plan Complex

For complex changes where the right approach isn't obvious, generate 2-3 viable options, compare tradeoffs, and recommend one. Saves the analysis for discussion before committing to an approach.

```
/plan-complex [description or context]

  1. Understand the problem and constraints
  2. Generate 2-3 viable approaches
  3. Analyze tradeoffs for each
  4. Recommend one with reasoning
  5. Save to options.md for discussion
```

## Step 1: Understand the Problem

Read the user's description and any referenced files. Before generating options, clarify:

- **Goal:** What is the desired outcome?
- **Constraints:** What can't change? (backwards compatibility, performance budget, API contract, timeline)
- **Scope:** What's in and out of scope?
- **Context:** What existing code/architecture does this interact with?

Scan the codebase for relevant files, patterns, and dependencies. Understanding the current state is essential for generating realistic options.

If the problem is underspecified, ask the user to clarify before proceeding. Do NOT generate options based on assumptions.

## Step 2: Generate Options

Produce **2-3 viable approaches**. Each option must be:

- **Feasible** — can actually be implemented given the constraints
- **Distinct** — meaningfully different from the others (not minor variations)
- **Complete** — includes enough detail to evaluate (files affected, rough scope, key decisions)

For each option, write:

```markdown
### Option A: [short name]

**Approach:** [1-2 sentence description of the strategy]

**How it works:**
- [Key implementation detail 1]
- [Key implementation detail 2]
- [Key implementation detail 3]

**Files affected:**
- `path/to/file` — [what changes]

**Estimated scope:** [small / medium / large]
```

Avoid generating a "do nothing" option unless it's genuinely viable. Avoid generating options that are clearly inferior just to have three — two strong options is better than two strong and one weak.

## Step 3: Analyze Tradeoffs

Compare all options across these dimensions:

```markdown
## Tradeoff Comparison

| Dimension | Option A | Option B | Option C |
|-----------|----------|----------|----------|
| **Complexity** | [low/med/high] | ... | ... |
| **Risk** | [low/med/high] | ... | ... |
| **Performance** | [impact] | ... | ... |
| **Maintainability** | [impact] | ... | ... |
| **Backwards compat** | [breaks/preserves] | ... | ... |
| **Time to implement** | [rough estimate] | ... | ... |
| **Testing effort** | [low/med/high] | ... | ... |
```

For each cell, add a brief explanation — not just "high" but "high — requires migrating all existing consumers."

Add a **Risks** section for each option:
- What could go wrong?
- What's the blast radius if it fails?
- What's the rollback story?

## Step 4: Recommend

Pick one option and explain why:

```markdown
## Recommendation: Option [X]

**Why:** [2-3 sentences explaining the reasoning]

**Key tradeoff accepted:** [What downside are we accepting and why it's acceptable]

**What would change this recommendation:** [Under what conditions would a different option be better]
```

Be opinionated. "It depends" is not a recommendation. If the options are genuinely close, say so and explain what additional information would tip the balance.

## Step 5: Save to File

Write the full analysis to `options.md` at the repository root:

```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
```

If `options.md` already exists, append with a horizontal rule separator.

**After saving, always print:**
```
Options analysis saved to: /absolute/path/to/options.md

Recommended: Option [X] — [one-line summary]

Review the analysis and tell me which option to proceed with.
```

Do NOT proceed to implementation. Wait for the user to choose.

## Step 6: Options Review Loop

After saving `options.md`, dispatch a **review agent** to critique the analysis. Iterate until the reviewer approves.

### Review Agent Instructions

Dispatch a subagent (via the Agent tool) with the following prompt:

> You are an options analysis reviewer. Read `options.md` and the referenced codebase files. Evaluate against these criteria:
>
> 1. **Factual accuracy** — Do the claims about the codebase hold true? Verify file paths, function names, and architectural claims by reading the actual code. Flag any claim that doesn't match reality.
> 2. **Distinct options** — Are the options genuinely different strategies, or minor variations of the same approach?
> 3. **Tradeoff accuracy** — Are the complexity/risk/performance assessments realistic? Is anything over- or under-estimated?
> 4. **Missed alternatives** — Is there an obvious approach that wasn't considered?
> 5. **Recommendation quality** — Is the reasoning sound? Does the accepted tradeoff make sense given the constraints?
> 6. **Completeness** — Are there missing risks, missing affected files, or gaps in the analysis?
>
> **IMPORTANT:** For each factual claim (e.g., "file X uses pattern Y", "module Z depends on W"), verify it by reading the actual code. Do not take the claims at face value.
>
> Output one of:
> - **APPROVED** — analysis is accurate and complete
> - **FEEDBACK** — list each issue with: section, problem, suggested fix
>
> Be strict on factual accuracy. Be practical on everything else.

### Review Loop

```
1. Save options.md (Step 5)
2. Dispatch review agent
3. If APPROVED → done, print options and wait for user
4. If FEEDBACK:
   a. Address each issue by updating options.md
   b. Re-dispatch the review agent
   c. Repeat (max 3 iterations)
5. If feedback remains after 3 iterations → print remaining feedback as warnings, proceed anyway
```

**After the loop completes, always print:**
```
Options reviewed and saved to: /absolute/path/to/options.md
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Generating options without understanding the codebase | Scan relevant files first — options must be grounded in reality |
| Options that are minor variations | Each option must represent a meaningfully different strategy |
| Skipping the tradeoff comparison | The comparison table is the most valuable part — never skip it |
| Recommending without reasoning | Always explain WHY, including what tradeoff you're accepting |
| Proceeding to implementation | STOP after saving options.md — wait for the user to choose |
| Generating options based on assumptions | If the problem is underspecified, ask for clarification first |
| "It depends" as a recommendation | Be opinionated. State what additional info would change the recommendation |
| Skipping the review loop | ALWAYS run the reviewer — it catches factual errors about the codebase |
| Claims about code without verifying | The reviewer MUST read actual files to verify claims, not take them at face value |
