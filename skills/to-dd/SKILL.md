---
name: to-dd
description: Use when the user wants to turn the current conversation into a short design document published as a claude.ai artifact, or invokes /to-dd.
---

# To DD

Turn the conversation and codebase into a **short design document a human actually
reads**, published as a **claude.ai artifact**. That artifact is the plan's single
source of truth: `/to-slices` writes the implementation plan into it and `/to-tasks`
writes the task map into it later. This skill creates **no GitHub issue** — the
tracker appears only when execution starts (`/to-tasks` opens it).

```
/to-dd [--title="..."] [--url=<artifact url>]

  1. Gather context (conversation + light repo read)
  2. Clarify gaps via AskUserQuestion   (gate, only if thin)
  3. Draft the doc
  4. Show it, wait for approval          (gate)
  5. Publish the artifact; print the URL
```

## Arguments

| Arg | Default | Notes |
|-----|---------|-------|
| `--title="..."` | Derived from context | The doc's title — what we're building |
| `--url=...` | Publish new | Re-publish: update that artifact in place, keeping any `Implementation plan` / `Tasks` content already on it |

## Phase 1 — Gather context

Read the conversation; explore the repo only if you haven't. Use the codebase's own
vocabulary and respect existing ADRs.

## Phase 2 — Clarify (gate)

If a fact that changes the design is missing, ask with **AskUserQuestion** (≤4 at a
time) — otherwise skip when context is rich. Every question offers concrete options,
and the recommended option's description states **why it wins** — the trade-off that
drives the pick. A bare "(Recommended)" with no reason is not an option.

## Phase 3 — Draft

**Write it tight — a beautiful blog post, not a spec:**

- Very short. Cut anything that doesn't change a decision or teach the reader.
- Plain English, no filler. Ban "robust", "seamless", "leverage", "comprehensive",
  "powerful" — and all hedging. Short declarative sentences. Concrete nouns.
- **Full sentences, never fragment bullets.** A list of three-word bullets that
  could caption anything ("improve UX", "add validation") is slop — if a point is
  worth listing, it is worth one real sentence that a reader can act on.
- Only what was discussed or confirmed — invent nothing.
- High level: name modules and capabilities, not file paths or code; they rot. Rare
  exception: a tiny snippet that nails a decision — a type, a schema.

**Explain with visuals.** Artifacts render mermaid natively — use a
`<pre class="mermaid">` block for anything structural: a flow, a pipeline, a
before/after architecture. When the subject is something on screen (a UI, a page, a
CLI), capture a screenshot of the current state and embed it as a data URI. One good
graphic per structural idea; no decoration for its own sake.

**The sections** (these exact five; the template carries their anchors):

| Section | What goes in it |
|---------|-----------------|
| The problem | What's wrong today, in the reader's words. One short paragraph. |
| User stories | A few: **what** the user does and **how** it plays out, each a two-or-three-sentence scene with a role label. |
| How it works | The key mechanics — short paragraphs, with a diagram where the shape matters. |
| Code change plan | **Module level only**: one row per module — `add` / `change` / `remove`, its name, and its interface in one phrase ("new module `slices` — owns the slice table and its ordering rules"). No code, no signatures, no file paths. |
| Decisions | Table: Area · Choice. |

`Implementation plan` and `Tasks` are **not yours** — their placeholders stay in
place for `/to-slices` and `/to-tasks`.

## Phase 4 — Approve (gate)

Show the draft in chat as plain markdown. Wait for an OK or edits. **Don't publish
until approved.**

## Phase 5 — Publish

Fill `~/.claude/at/templates/design-doc.html` (or the repo's copy at
`templates/design-doc.html`). It carries the design, the section ids, and — in its
`SLOT` comments — what this skill fills versus what it must leave alone; mirror its
example markup and keep its class names and section ids. Write the filled page to the
session scratch directory, never the target repo, as
`design-doc-<owner>-<repo>-<slug>.html` (`gh repo view --json owner,name`, owner is
`.owner.login`; slug from the title).

Neither template copy present — the staged extra lags a reinstall — → degrade to a
self-styled page that keeps the **same section ids and heading text** so downstream
skills still find their anchors, and tell the user to reinstall the `to-dd` package
to get the designed skeleton back.

Publish with the Artifact tool — `<title>` = the doc title, favicon `📐` (stable
across republishes), a one-sentence gallery description. With `--url`, pass it as the
`url` parameter so that artifact updates in place — and first read the current page
(WebFetch) to carry its `Implementation plan` and `Tasks` sections forward verbatim;
this skill owns every other section. No Artifact tool (headless) → **stop**: the doc
*is* the artifact, so report that `/to-dd` needs an artifact-capable session.

**The artifact is the only output.** No GitHub issue, no file in the target repo, no
side summary — the chat report below is one line.

## Report

End with one parseable line — `/to-slices` and `/to-tasks` scan for it:

```
Design doc published: <artifact url>
```

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Creating a GitHub issue | Never — `/to-tasks` opens the tracker when execution starts |
| Overwriting `Implementation plan` / `Tasks` on a re-publish | Read the live page first; those sections belong to the other skills |
| Spec voice ("the system shall…") | A blog post: short scenes, active verbs, concrete nouns |
