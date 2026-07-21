---
name: grill-me
description: Use when the user wants their plan, decision, or idea stress-tested through a relentless one-question-at-a-time interview that leaves a live decision-record artifact — the user says "grill me", "stress-test my thinking", "poke holes in my plan", "interview me about" — or invokes /grill-me.
---

# Grill Me

**Interview the user relentlessly about a plan, decision, or idea until you reach a
shared understanding** — and leave behind a decision record.

```
/grill-me <topic>

  1. Map      the decision tree      (branches → questions)
  2. Publish  the live page          (question up top, map + record below)
  3. Grill    one question at a time (recommendation + reasoning)
  4. Converge and confirm            (the record stands)
```

## Phase 1 — Map the tree

- Pin the subject in one sentence. Missing or vague → ask for it in chat first; the
  subject question is exempt from the protocol — no page entry, no recommendation.
- Break the subject into **branches** (3–6), each holding 1–3 questions — aim for
  6–12 total — ordered so upstream decisions come first.
- Look up every fact you can — filesystem, git, `gh`, docs, `WebSearch`. Only
  decisions go to the user.
- What the user's opening message (the brief) already decided enters
  **Already settled** — never re-asked.

## Phase 2 — Publish the live page

Load the `artifact-design` skill before building (and `dataviz` before any chart).
Write the page to the scratchpad and publish with the `Artifact` tool before the
first grilled question; share the link in chat. At first publish pick the emoji
favicon, `<title>` (the subject), and the one-line gallery `description` — favicon
and `description` never change; re-title only if a reversal changes the subject.
The first question in map order opens the grill.

The page, top to bottom:

1. **Header** — eyebrow (session date), title, one-sentence dek stating what's
   being decided and the stakes.
2. **On the grill now** — the current question: its branch, why it matters, the
   recommendation with its trade-off (closed: options with the recommended one
   badged; open: prose), and a note that answers happen back in chat (closed: pick
   or type; open: type freely).
3. **The decision map** — every question, numbered `Q1…` (numbers never change),
   under its branch with a state pill: `ON THE GRILL`, `QUEUED`, or
   `SETTLED → <one-phrase outcome>`. Grilled answers appear both here and in
   **Already settled**; brief-settled decisions live only in **Already settled**.
4. **Already settled** — one line per decision with its source (the brief, a question
   number, a mid-session correction).
5. **The story so far** — short blog-voice paragraphs: what was decided and *why*,
   one paragraph per branch as it closes.

Sections render only once they have content. Beyond the always-on map, a question
earns its own graphic only when the choice is visual or structural (side-by-side
mockups, a trade-off table, a small mermaid diagram).

## Phase 3 — Grill

One question at a time, each carrying **a recommended answer and the trade-off that
drives the pick**.

- **Closed** (2–4 genuinely distinct designs) → `AskUserQuestion`, recommended option
  first with `(Recommended)` in its label and the trade-off in its description.
  Typing a free answer always works.
- **Open** ("what's the real goal?") → plain prose in chat. Never manufacture options
  for an open question — options anchor the user to your framing.

Route every answer — apply each bullet that matches; when bullets disagree on what
takes the grill next, the reversal's ordering wins:

- Answers the question (or any queued one) → settle it; the first `QUEUED` question
  takes the grill — re-opened ones first, upstream-first, then map order.
- Raises a new question → queue it under its branch (new branch if none fits), next
  unused number.
- Corrects *how you're asking* → into **Already settled** as a mid-session correction.
- Reverses a settled decision → it re-opens, along with every decision that assumed
  it, directly or through another re-opened one; any re-opened decision without a
  number gets the next unused one under its branch (new branch if none fits). If the
  user named the replacement, the reversed decision re-settles immediately; otherwise
  it takes the grill next. The rest return to `QUEUED` and take the grill one at a
  time, upstream-first, before any previously queued question.
- Calls it early ("that's enough", "go with your recommendations") → settle each
  remaining question with its recommendation, marked on the page as an agent pick —
  or as open if there is none — and go to Phase 4.
- Still unanswered after routing, and nothing else claimed the grill → re-pose the
  grilled question.

**After routing, make the page true again, then redeploy the same path before asking
on.** Pills, **Already settled** lines, and story paragraphs always match what is
currently decided: a re-opened decision loses its **Already settled** line, and its
branch's story paragraph is rewritten if part of the branch still stands, removed if
nothing does, restored when the branch re-closes.

## Phase 4 — Converge and confirm

When every branch is settled (check after each routing pass):

1. Restate the whole design in a few tight paragraphs in chat. On the page, add
   **The shared understanding** directly under the header, with **On the grill now**
   beneath it showing the confirmation question (no branch line; it never enters the
   map); redeploy before asking.
2. Confirm via `AskUserQuestion`: `Confirmed (Recommended)` plus `Adjust`, each with
   a one-line description. On `Confirmed` → step 3. A bare `Adjust` gets one prose
   follow-up — what changes? (A typed correction routes directly.) Route corrections
   by Phase 3's rules. If any branch is no longer settled — a reversal or a new
   question — pull **The shared understanding** off the page and return
   **On the grill now** to its Phase 2 slot, grilling resumed by Phase 3's ordering,
   until every branch settles again. Any change — even one that re-settles
   immediately — reruns Phase 4 from step 1.
3. On confirmation, remove **On the grill now** and redeploy one last time: the rest
   of the page stands as the **decision record** at the same URL — the session's
   only output (no repo copy).
4. If the subject is something to build, offer in chat — never auto-run — the
   `/to-prd` → `/breakdown` handoff.

Do not act on the subject before the confirmation.

## The voice

Blog-post voice on the page and in chat: short sentences, active verbs, concrete
nouns, no filler — a teammate who missed the session should get each decision and its
*why* in one read.

**Banned words:** leverage, robust, seamless, comprehensive, powerful, streamline, utilize,
facilitate, ensure, delve, furthermore, moreover, "in order to", "it's worth noting",
"game-changer", "not only… but also".

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Asking the user a fact | Look it up first |
| Batching questions | One at a time — the next depends on this answer |
| Options for an open question | Prose only |
| Letting the page lag | Redeploy after every answer |
| Reversing a decision, keeping its dependents | Purge them from **Already settled**; re-open their questions |
| Acting before confirmation | The record stands first |
