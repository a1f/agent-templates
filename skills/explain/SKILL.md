---
name: explain
description: Use when the user wants a dead-simple, plain-words explanation of a slice or a PR — why we need it, what it is, what changes — or invokes /explain.
---

# Explain

**Explain a slice or a PR in plain words** — for someone who has never seen the code.

Do it the way *Thing Explainer* does — hard things in common words, so a pencil
becomes a "writing stick." Show the **impact**, not the mechanics.

```
/explain <id> [--issue=N]

  <id> = a slice (4, 7), a PR row (4.2, 5.1), or a GitHub PR (#92)

  1. Find  the slice or PR   (don't guess; ask if unsure)
  2. Read  just enough       (the row + the "why", never the whole diff)
  3. Write it plain          (2–3 short paragraphs)
```

## Phase 1 — Find the slice or PR

Resolve `<id>` in this order:

1. **Empty** → ask which slice or PR they mean (or offer the current branch's PR,
   `gh pr view --json title,body`).
2. **`#92` or `PR 92`** → a GitHub PR. `gh pr view 92 --json title,body,files`;
   take the "why" from its body (no such PR → ask). Go to Phase 3.
3. **A bare or dotted number** → open the plan issue (`gh issue view <N> --json body`)
   and match the id *whole* against both tables; the table it sits in decides — **PR
   breakdown** → PR row, **slice** table → slice (including a hand-inserted `4.5`).
   Whole-cell, so `4.2` ≠ `14.2`.
4. **No single match** → a whole number may be a GitHub PR; confirm "Did you mean PR
   #<id>?" before `gh pr view <id> --json title,body`. If it errors, the id is dotted,
   or both tables match, ask which they mean.
5. **Anything else** (a word, a slug) → ask which slice or PR they mean.

Find the plan issue: `--issue=N` if given, else `gh issue list --state all --label Plan`,
then `gh issue list --state all --search "Build plan in:body"`. One match, use it;
many, narrow then ask; zero, ask — show the issue # and title.

## Phase 2 — Read just enough

Pull the facts, not the whole diff:

- **Slice or PR row** → its row, and the issue's `## The problem` /
  `## What we're building` for the "why". For a slice, also the PRs under it; for a
  PR row, its parent slice.
- A PR row often links its merged PR (a `#number`); else find it unmistakably
  (`gh pr list --state all --search "<words from the row>"`) and read its title and
  body. On zero or many matches, stay with the issue facts.

Never invent.

## Phase 3 — Write it plain

Two or three short paragraphs, in this order:

1. **Why we need it** — what's wrong or missing today. What hurts.
2. **What it is** — name the thing in one plain phrase, like "one command: `at update`".
3. **What changes** — what you can do after that you couldn't before.

If the source is too thin for a real "why", say so and ask for one sentence of intent.

### The voice

The `english` rule governs every word — it loads each session, so you already have it.
Two additions this skill owns:

- If a code word is the only fit (symlink, hash, CI), say what it does in plain words
  right after — once.
- Talk to the reader: "you", "your".

Read the draft against the rule before you print it, and fix what it catches.

Under ~150 words. Plain paragraphs — no bullets or emoji. Print it in chat; post it
to the PR or issue only if they ask.

## Example — a slice (`/explain 4.5`)

> Right now the only way to know the installer works is to run it by hand and look.
> You tick a skill, then dig through your files to check it really showed up. That's
> slow, and it's easy to miss something broken.
>
> This slice adds an automatic test. It runs the real installer the same way you would,
> installs a skill, then writes down every file it made and saves the list. Run it
> again later and it checks the new list against the saved one; if anything differs,
> it stops and tells you.
>
> So nobody tests by hand anymore. The test runs the same steps every time and
> catches a break the moment it happens — long before it reaches a real person.

## Example — a PR (`/explain 4.2`)

> Before this, the installer couldn't safely pull new versions of skills. To get one
> you re-installed it — copying the new files over the top, which could wipe a change
> you'd made yourself.
>
> This PR adds one command: `at update`. It grabs the newest skills, works out which
> ones actually changed, and only replaces those. If your hand-edited copy would be
> overwritten, it saves it first as a `.bak` file so nothing is lost.
>
> So updating is safe and small now. You get the new stuff, untouched skills are left
> alone, and your own edits are kept instead of thrown away.

## Common mistakes

| Mistake | Fix |
|---------|-----|
| Explaining the mechanics, not the impact | Answer "what can the reader now do?" |
| Inventing a "why" the work never states | Pull it from `## The problem`; if it's not there, ask |
| Reading the wrong PR from a loose search | The match must be unmistakable, or use the issue facts |
