---
name: review-and-fix-that
description: Use when the user wants a plan or technical document critiqued by multiple independent perspectives and the critiques addressed, or invokes /review-and-fix-that. Inspects the target, selects 5 applicable reviewers from a lens palette, aggregates their feedback, addresses each comment, and returns a summary.
---

# Review And Fix That

Critique a plan or technical document (`plan.md`, `architecture.md`, `options.md`, design doc, README, tutorial, API reference, PR description, …) by inspecting the target, dispatching **5 fully independent reviewers in parallel** with lenses that fit the target, then addressing each comment and reporting a summary.

```
/review-and-fix-that [path | description of the target]

  1. Resolve the target and select 5 applicable reviewers
  2. Dispatch the 5 reviewers in parallel
  3. Aggregate comments
  4. Address each comment (edit target, or record a dismissal reason)
  5. Print summary
```

## Step 1: Resolve the Target and Select 5 Reviewers

### 1a. Resolve the Target

Determine what is being reviewed. In order of preference:

1. An explicit path the user gave (`/review-and-fix-that plan.md`, `/review-and-fix-that docs/auth.md`)
2. A standard planning file at the repo root (`plan.md`, `architecture.md`, `options.md`) — if exactly one exists and the user did not name one, use it
3. A document referenced in the conversation — confirm the path with the user before proceeding
4. Free-form content from the conversation — write it to a temporary file at `$(git rev-parse --show-toplevel)/review-target.md` before reviewing, so reviewers have a stable artifact to read

If the target is ambiguous (multiple candidate files exist, nothing referenced), **ask the user which one**. Do not guess.

Read the target in full before selecting reviewers — you need to understand what the document actually is.

### 1b. Inspect the Target

Classify the target. Look at:

- **Filename + location** — `plan.md`/`architecture.md`/`options.md` signals a proposal; `README.md`/files under `docs/` signals documentation; `api/*.md` or reference material signals a spec; `tutorial/`, `guides/`, `how-to/` signals a walkthrough
- **Stance** — does it describe *what we'll build* (plan/proposal) or *what exists* (documentation)? Future tense + "we'll", "the approach", "this change" → plan. Present/imperative + "returns", "usage", "run this" → docs
- **Audience** — reviewers of a change (plan) vs end users / operators / integrators (docs)
- **Failure mode if wrong** — a project goes sideways (plan) vs a reader gets stuck (doc)

Name the kind — one of: **plan**, **proposal**, **design**, **API reference**, **tutorial**, **README**. If the target mixes two kinds, tag it **hybrid: <kind-A> + <kind-B>** and pick a blend below.

### 1c. Select 5 Reviewers from the Palette

The palette:

| Lens | Best for | Signal |
|------|----------|--------|
| **Correctness** | Plans, proposals, procedures | Does the approach logically produce the claimed result? |
| **Completeness** | Anything | Gaps vs stated scope |
| **Simplicity** | Plans, designs | Over-engineering, unjustified abstraction (YAGNI) |
| **Risk** | Plans, changes, proposals | Failure modes, blast radius, reversibility |
| **Alternatives** | Plans, designs | Missed approaches, reinvented wheels |
| **Accuracy** | Docs, references, tutorials | Claims about code/behavior match reality |
| **Clarity** | Docs, prose-heavy content | Unambiguous wording, jargon defined, references resolve |
| **Audience fit** | Docs, tutorials, READMEs | Right assumed knowledge for the stated reader |
| **Structure** | Docs, long-form content | Logical flow, heading hierarchy, navigable order |
| **Example coverage** | Tutorials, API references, READMEs | Concrete examples that back every non-obvious claim |

Pick exactly **5** that apply most to this target. Starting points — override when the target doesn't fit:

| Target kind | Default 5 |
|-------------|-----------|
| **Plan / proposal / design** | Correctness, Completeness, Simplicity, Risk, Alternatives |
| **API reference / spec** | Accuracy, Completeness, Clarity, Structure, Example coverage |
| **Tutorial / how-to** | Accuracy, Clarity, Audience fit, Example coverage, Structure |
| **README** | Completeness, Clarity, Audience fit, Example coverage, Structure |
| **Hybrid** | Pick 2-3 plan lenses + 2-3 doc lenses in proportion to which side dominates |

**Tiebreak** — if more than 5 lenses look equally applicable, pick the 5 whose focus definitions have the least overlap so coverage stays broad. When two lenses would catch the same issue from different angles, keep one and drop the other.

**Hybrid Completeness rule** — if Completeness is among your 5 and the target is hybrid, pick the plan or doc flavor of its focus based on which aspect is more load-bearing. If both are load-bearing, concatenate both focus texts in that reviewer's prompt.

Write down the chosen 5 before dispatching — they go into each reviewer's prompt.

## Step 2: Dispatch the 5 Reviewers in Parallel

Take the 5 lenses from Step 1c. Dispatch one reviewer per lens, all 5 in a **single message with 5 parallel `Agent` tool calls** — see **Independence Rules** below for the non-negotiables before dispatching.

### Focus Definitions

Look up each chosen lens below and grab its focus text — you'll paste it into that reviewer's prompt as `{{FOCUS}}`.

**Plan lenses:**
- **Correctness**: Steps that don't produce the claimed result; logical contradictions; assumptions that don't hold in the codebase; ordering issues (step B depends on something step A removed); mismatches between inputs/outputs of successive steps.
- **Completeness** *(plan)*: Requirements from the goal not covered by any step; missing error/edge cases (empty input, failure mid-way, partial success); missing rollback/cleanup; undocumented preconditions; handoffs between components that aren't spelled out.
- **Simplicity**: Abstractions introduced for imagined future needs; configurability with no second caller; new modules where an existing one would do; design patterns where 3 lines would do; indirection without justification.
- **Risk**: What happens if a step fails halfway; operations that aren't reversible; blast radius of a bug; shared-state changes; data loss potential; ordering dependencies that break under concurrency or retries.
- **Alternatives**: Existing utilities/modules in the codebase the plan reimplements; a simpler approach the plan overlooked; a library or built-in that fits; a different decomposition that eliminates whole steps.

**Doc lenses:**
- **Accuracy**: Claims about code, APIs, or behavior that don't match reality; code examples that don't run; signatures that drifted; outdated references to files or flags; named entities that no longer exist.
- **Clarity**: Ambiguous prose; pronoun references that don't resolve; jargon used before it's defined; sentences that require re-reading to parse; terms used inconsistently (two names for one concept, or one name for two concepts).
- **Completeness** *(doc)*: Missing sections for the stated scope; missing prerequisites; missing caveats/limitations; obvious questions left unanswered; no "what next" or cross-reference when the reader's journey continues elsewhere.
- **Audience fit**: Assumed knowledge mismatches the stated/implied reader — either over-explaining basics or under-explaining novel concepts; examples that don't resonate with the target audience; density too high or too low for the reader's goals.
- **Structure**: Illogical flow (reference before concept, usage before setup); heading hierarchy that hides important sections; related content scattered; surprising ordering that forces scrolling back; missing TOC or navigation when length warrants one.
- **Example coverage**: Non-obvious claims asserted without a concrete example; examples that cover the happy path but no failure/edge cases; examples that don't actually demonstrate what the surrounding prose claims.

### Reviewer Prompt (same template, different lens)

Pass this prompt to each reviewer, substituting `{{LENS}}`, `{{FOCUS}}`, and `{{TARGET_PATH}}`:

> You are an independent reviewer with the lens of **{{LENS}}**. Read the target document at `{{TARGET_PATH}}` and any files/APIs/code it references. Verify factual claims by reading the actual source — do not take claims at face value.
>
> **Your focus:** {{FOCUS}}
>
> **Out of scope for you:** other lenses (another reviewer has them). Stay in your lane. Flagging something outside your lens dilutes the signal.
>
> **Output format** — a JSON array, one object per comment:
>
> ```json
> [
>   {
>     "severity": "CRITICAL | MAJOR | MINOR",
>     "location": "section heading or quoted line from the target",
>     "comment": "One-sentence description of the problem",
>     "suggestion": "Concrete fix — what to change and to what"
>   }
> ]
> ```
>
> Severity rubric:
> - **CRITICAL**: the target will fail at its purpose if this isn't fixed (plan won't work; reader can't accomplish the documented task)
> - **MAJOR**: the target is materially incomplete or risky; addressing this meaningfully improves it
> - **MINOR**: nit, polish, small clarity improvement
>
> Return `[]` if you find nothing worth flagging. Do NOT invent issues to seem thorough. Do NOT speculate about what other reviewers might say.

### Handling Failures

- **Target unreadable** (missing, binary, permission denied): stop before dispatching and report the error to the user.
- **Reviewer returns malformed output** (not a JSON array, missing fields, invalid severity): treat that reviewer's contribution as `[]` and tag its lens as `failed` in the Step 5 summary header.
- **Two or more reviewers fail:** stop and report — don't proceed with weak coverage.

## Step 3: Aggregate Comments

Collect all JSON arrays. Build a combined list:

```
[
  {reviewer: "Correctness",  severity: ..., location: ..., comment: ..., suggestion: ...},
  {reviewer: "Completeness", ...},
  ...
]
```

**Dedupe.** Two comments share "the same underlying issue" when both point to the same sentence/section **and** identify the same defect (e.g., both flag "missing null check" at line 42, even in different words). When in doubt, keep both — false dedupe loses information; false non-dedupe just lengthens the list.

- Keep one entry, set `reviewer` to a comma-joined list (`"Correctness, Risk"`)
- Take the highest severity
- Merge suggestions when they agree

**Contradictory suggestions.** If two reviewers propose opposite fixes for the same location (A: "add X"; B: "remove X"), **do not dedupe**. Keep both as separate entries and mark each with `"conflict_with": "<other reviewer>"`. Resolve the contradiction in Step 4 by picking one, partial-addressing both, or dismissing both with a reason.

**Order** the final list by severity DESC, then by reviewer count DESC, then by order-of-appearance.

## Step 4: Address Each Comment

Walk the list in order. For every comment, decide **one** of:

| Decision | When | Example |
|----------|------|---------|
| **Address** | Comment is correct; the suggested fix (or an equivalent) should land in the target | Reviewer flags "missing null check on line 42" — add the check |
| **Partial** | The comment bundles multiple claims; some are valid, some aren't | Reviewer raises two issues in one entry; one is real, one is a misread — apply the real fix, record why the other was deferred |
| **Dismiss** | Comment is wrong (misreads the target or code), out of scope, or a lens overreach | Reviewer from the Correctness lens flags a wording nit — dismiss as lens overreach |

Edit the target file with the `Edit` tool — one change per comment so it's traceable. After addressing a CRITICAL or MAJOR comment, re-read the surrounding section to confirm the fix is coherent. After editing, sanity-check the target is still well-formed (valid markdown, runnable code blocks, resolving cross-references).

**Do not blindly apply every suggestion.** Reviewers are fallible. If a critique rests on a misreading of the target or the code, dismiss it with a one-sentence reason. Sycophancy toward reviewers is as bad as sycophancy toward users.

Track the decision for each comment in memory — you'll need it for Step 5. Create a tracking file (`$(git rev-parse --show-toplevel)/review-tracking.md`) only when the comment count **exceeds 20**; at that scale conversation context becomes unreliable.

## Step 5: Print Summary

After all comments are processed, print:

```
# Review Summary — <target path>

Kind: <plan | API reference | tutorial | README | hybrid: …>
Reviewers: <5 lens names>
Comments raised: N

## Addressed (K)
- **[severity]** <comment>  →  <what changed in the target, file:line or section>
- ...

## Partial (J)
- **[severity]** <comment>  →  <what was applied>; deferred: <what + why>
- ...

## Dismissed (M)
- **[severity]** <comment>  →  <one-sentence reason>
- ...

Target updated at: <absolute path>
```

Keep each line to one sentence. The goal is a scannable log, not a report.

If any CRITICAL comment was dismissed, call that out explicitly at the top so the user can push back.

**Where the output goes.** Print the summary to stdout (the conversation). Leave all target edits **uncommitted** so the user can review the diff and commit them if they choose — do not `git add` or `git commit` from within this skill. If a tracking file was created in Step 4, point to it in the summary header.

## Independence Rules

Independence is the whole point of dispatching 5 reviewers — if you compromise it, the signal collapses.

- Dispatch all 5 reviewers in **one message with 5 parallel `Agent` tool calls**. Do not dispatch sequentially; do not share outputs between them.
- Do not tell any reviewer what the others were asked to look at beyond their own lens.
- Do not pre-filter the target before handing it off — every reviewer sees the same text.
- When addressing comments in Step 4, do not re-dispatch reviewers on the updated document. One pass is the contract of this skill. If the user wants iteration, they can invoke `/review-and-fix-that` again on the updated target.

## Quick Reference

| Step | Action | Output |
|------|--------|--------|
| 1 | Resolve target + select 5 reviewers from palette | Target path + chosen lens list |
| 2 | Dispatch 5 reviewers in parallel | 5 JSON arrays of comments |
| 3 | Aggregate + dedupe | Ordered comment list |
| 4 | Address each (edit / partial / dismiss) | Updated target file + decisions |
| 5 | Print summary | Scannable log of what changed |

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Always using the same 5 lenses | Inspect the target — a tutorial needs Clarity and Audience fit, not Risk and Alternatives |
| Picking more or fewer than 5 reviewers | Exactly 5. Too few dilutes coverage, too many reduces per-lens depth |
| Dispatching reviewers sequentially | One message, 5 parallel `Agent` calls — always |
| Telling reviewers what other lenses are checking | Each reviewer sees only their own lens |
| Re-dispatching reviewers after addressing comments | One pass. If more review is needed, the user re-invokes the skill |
| Applying every suggestion blindly | Dismiss wrong critiques with a reason — reviewers are fallible |
| Skipping the summary | The summary is the deliverable — without it, the user has to re-derive what changed |
| Silently addressing CRITICAL dismissals | If a CRITICAL is dismissed, surface it at the top of the summary |
| Inventing a target when none is specified | Ask the user which document to review rather than guessing |
| Creating tracking files for small comment lists | Use conversation context; only write a tracking file if >20 comments |
| Letting one reviewer's work leak into another's prompt | Agents must be fully independent — no shared state, no shared output |
