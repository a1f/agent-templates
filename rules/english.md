---
paths: "**/*", "*"
---

# English Rules

Every word we emit: chat replies, artifact pages, PR bodies, issue text, commit messages,
code comments, agent briefs, error strings. Adapted from ASD-STE100 Simplified Technical
English (Issue 9), the aerospace standard for instructions a technician cannot misread.
Our reader has no back-channel either. Write for one reading.

Two faults break one reading: a word with more than one meaning, and a sentence with more
than one possible structure. Every rule below removes one of them.

## Words

- **One word, one meaning.** Give a concept one word and use that word everywhere. Never
  use one word for two concepts. A `slice` is the vertical unit of work, and nothing else.
- **Concrete nouns.** Name the real thing. `functionality`, `capability`, and `solution`
  name nothing.
- **The commonest word wins.** `use`, not `utilize`. `about`, not `regarding`. `start`, not
  `initiate`. Take the short common word before the formal one.
- **Approved terms are the names already in the tree** — `slice`, `unit`, `package`,
  `extra`, `hook`, `gate`, `artifact`. Use the tree's spelling. A new term earns its place
  once, in plain words, then stays fixed.
- **No synonym for variety.** Repeat the noun. A fresh word makes the reader ask whether
  you mean a fresh thing.

**Banned words:** leverage, robust, seamless, comprehensive, powerful, streamline, utilize,
facilitate, ensure, delve, furthermore, moreover, "in order to", "it's worth noting",
"game-changer", "not only… but also".

**Banned moves:** the rhetorical question. The wind-up before the point. The summary that
repeats what the reader just read. The apology. The adjective that carries no data — write
"2× faster", not "significantly faster".

## Grammar

STE restricts verb forms, because a compound tense hides who acts and when.

| Use | Do not use |
|-----|-----------|
| infinitive, imperative | present perfect — "we have added" |
| simple present, simple past, simple future | past perfect, future perfect |
| past participle **as an adjective** — "the staged copy" | continuous forms as verbs — "we are adding" |

- **An `-ing` word is a noun or it is gone.** "the sizing rule" holds. "we are staging the
  unit" does not — write "we stage the unit".
- **Active voice in every instruction.** "The gate reads the diff", not "the diff is read".
  Take passive voice only in description, and only when the actor is unknown.
- **Drop no words.** Keep the article, the subject, the verb. STE says plainly that a cut
  word buys length and pays in ambiguity.

## Sentences

- **20 words** is the cap for an instruction — a sentence that tells someone to act.
  **25 words** is the cap for every other sentence.
- **One instruction per sentence.** Two actions are two sentences.
- **Three words is the cap for a noun cluster.** "prompt lint check" reads. "prompt lint
  check failure report" is not a phrase, it is a puzzle.
- **The condition comes first:** "If the file is absent, skip the step."

## Paragraphs, lists, and emphasis

- **One topic per paragraph, six sentences at most.**
- **A list carries a sequence, a set of conditions, or three or more parallel items.**
  Nothing else. Two items are a sentence.
- **Prose is the default.** An answer built only from bullets is an outline, not an
  explanation, and the reader must rebuild every connection you dropped. Put bullets under
  a sentence that says what they are.
- **Emphasis is rare by definition.** Bold the term the reader will search for. Bold every
  line and you emphasize nothing.
- One em-dash aside per paragraph at most. No emoji in prose.

## Pictures

A picture earns its place when it shows what prose must spell out slowly.

| Draw it | Write it |
|---------|----------|
| the thing has a shape — tree, graph, layout | it is one fact |
| steps flow into each other | it is one comparison |
| three or more things differ on two or more axes | the picture would restate the sentence |
| before against after | you fill space |
| numbers carry the argument | |

A picture shows the real mechanism, with the real names from the tree. A decorative
diagram costs a read and returns nothing, so it is worse than no diagram. When the
`artifact-diagramming` or `dataviz` skills are available, they own how to draw one.

## Where these rules stop

Quoted material, command output, code, test names, existing API and file names, and anyone
else's words stay verbatim. Never rewrite a quote into STE.

## Self-check

Read the draft once against this file before you publish a page, a PR body, or an issue.
Fix what it catches, then name the fixes in your report: which rule, which sentence.
