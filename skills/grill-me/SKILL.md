---
name: grill-me
description: Use when the user wants their plan, decision, or idea stress-tested through a relentless one-question-at-a-time interview — says "grill me", "stress-test my thinking", "interview me about" — or invokes /grill-me.
---

# Grill Me

**Interview the user relentlessly about a plan, decision, or idea until you reach a
shared understanding** — and leave behind a decision record they can hand to a teammate.

Walk the decision tree branch by branch, resolving dependencies between decisions
one by one. Facts get looked up; only decisions get asked. Nothing is acted on until
the user confirms the shared understanding.

```
/grill-me <topic>

  1. Map      the decision tree     (branches → questions; look up every fact first)
  2. Publish  the live page         (question on top, map, record below)
  3. Grill    one question at a time (recommendation + reasoning, always)
  4. Converge and confirm           (shared understanding → the record stands)
```

## Phase 1 — Map the tree

- Pin the subject in one sentence. If the topic is missing or vague, that's the first
  open question — ask it.
- Break the subject into **branches** (3–6), each holding 1–3 questions. Order them so
  upstream decisions come first: a branch whose answers depend on another waits.
- **Look up every fact you can** — filesystem, git, `gh`, docs, tools. A question the
  environment can answer is never put to the user. The *decisions* are theirs alone.
- Note what the user has already decided (their brief, earlier messages). Those enter
  the record as settled, sourced to them — never re-asked.

## Phase 2 — Publish the live page

From the first question, the session has an artifact. Load the `artifact-design`
skill before building it (and `dataviz` before drawing any chart). Keep the file in
the scratchpad and redeploy the same path so the URL never changes.

The page, top to bottom:

1. **Header** — eyebrow (session date), title, one-sentence dek naming the subject.
2. **On the grill now** — the current question: its branch, why it matters, the
   options with the recommended one visually flagged, and a note that answers happen
   in the terminal (pick or type).
3. **The decision map** — every question under its branch with a state pill:
   `ON THE GRILL` / `QUEUED` / `SETTLED →` one-phrase outcome. Hot questions carry
   the accent color; settled ones cool to a muted tone.
4. **Already settled** — one line per decision with its source (their brief, a
   question number, a mid-session correction).
5. **The story so far** — the record as short blog-voice paragraphs: what was
   decided and *why*, one paragraph per branch as it closes.

**Redeploy after every answer.** The settled question cools into the map and record;
the next takes the grill. A page that lags the terminal can't be trusted, and a page
that can't be trusted isn't worth having.

**Graphics inform or don't exist.** The map is always on. A question earns its own
graphic only when the choice itself is visual or structural — layout mockups side by
side, a trade-off table, a small mermaid diagram. Never illustrate a verbal question.

## Phase 3 — Grill

One question at a time. Multiple questions at once are bewildering.

Every question carries **a recommended answer and the actual reasoning behind it** —
the trade-off that drives the pick, not just the pick. A recommendation without its
why is an instruction, not an argument.

Delivery adapts to the question's shape:

- **Closed** (2–4 genuinely distinct designs exist) → `AskUserQuestion`, recommended
  option first and marked `(Recommended)`. The user can always type their own answer
  instead — options are an offer, never a cage.
- **Open** ("what's the real goal?", "what does success look like?") → plain prose in
  chat. Do not manufacture options for an open question; invented options anchor the
  user to your framing instead of extracting theirs.

Answers feed back into the tree: a reply that raises a new question queues it in the
map; a correction of *how you're asking* becomes a settled rule for the rest of the
session, on the record like any other decision.

## Phase 4 — Converge and confirm

When every branch is settled:

1. Rewrite the page's top section as **the shared understanding** — the whole design
   in a few tight paragraphs — and restate it in chat.
2. Ask the user to confirm, correct, or send a question back to the grill.
3. On confirmation, the page sheds its live scaffolding (hot seat off, map fully
   cooled) and stands as the **decision record** at the same URL — that record is the
   session's output.
4. If the grilled subject is something to build, offer — never auto-run — the
   `/to-prd` → `/breakdown` handoff. The record is most of a PRD already.

**Do not act on the subject before the confirmation.** The grilling exists to replace
guessing with agreement; acting early forfeits that.

## The voice

Blog-post voice, on the page and in chat: short sentences, active verbs, concrete
nouns, no filler. Write the record so a teammate who missed the session understands
each decision *and its why* in one read. Never pad — a settled decision is one line
in the map, one sentence in the settled list, and earns a paragraph only when its
reasoning needs one.

**Banned:** leverage, robust, seamless, comprehensive, streamline, utilize,
facilitate, delve, furthermore, "in order to", "it's worth noting".

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Asking the user a fact | Look it up — filesystem, git, `gh`, tools. Only decisions go to the user |
| Batching questions | One at a time; the next question often depends on this answer |
| A pick without its why | Every recommendation states the trade-off that drives it |
| Options for an open question | Open questions are prose; invented options anchor |
| Re-asking what the brief already decided | Enter it as settled, sourced to the user |
| Letting the page lag | Redeploy after every answer, same file path, same URL |
| Decorating verbal questions | A graphic must carry what prose can't, or not exist |
| Acting before confirmation | The record stands first; the building starts after |
