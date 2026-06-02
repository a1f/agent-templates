---
paths: "**/*.py", "**/*.ts", "**/*.tsx", "**/*.rs", "**/*.go", "**/*.java", "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp"
---

# Design Principles

Language-agnostic rules for structure, abstraction, and readability. Language rules
(`python.md`, `typescript.md`, …) govern *syntax and idiom*; this file governs *design*.
Based on Ousterhout's *A Philosophy of Software Design*. These apply to every change,
however small.

## Contents

- The one goal: minimize complexity
- Deep modules
- Information hiding
- Layers and abstraction
- General-purpose interfaces
- Define errors out of existence
- Naming
- Comments
- Tactical vs strategic
- Red flags
- Testability is a design property

## The one goal: minimize complexity

Complexity is anything about the structure of a system that makes it hard to understand
or modify. It is the enemy; everything else here serves this goal. Watch for its three
symptoms and treat any of them as a defect:

- **Change amplification** — a simple change requires edits in many places.
- **Cognitive load** — a developer must hold a lot in their head to make a change.
- **Unknown unknowns** — it is not obvious which code must change, or what a change will break.

Complexity is incremental: it accrues one "this'll do" at a time. Reject those individually.

## Deep modules

A module (function, class, file, service) is an interface plus an implementation. The best
modules are **deep**: a simple interface hiding a powerful implementation. The cost of a
module is its interface (what every caller must learn); the benefit is its implementation.

- Prefer few deep modules over many shallow ones. A class/function whose interface is as
  complex as its body (a "shallow module") adds cost without hiding anything.
- Beware *classitis*: chopping logic into many tiny classes/functions that each do almost
  nothing but together force the reader to chase the flow across files.
- A method/function should have a clear, single abstraction. If you cannot state what it
  does in one short phrase without "and", it is doing too much.

## Information hiding

Each module should encapsulate a few design decisions that nothing outside it depends on.
That is what makes interfaces simple and change local.

- **Keep each design decision in one place** (no information leakage): a file format, a
  protocol detail, or a default should live in a single module. If changing one forces a
  change in another, the knowledge leaked — pull it into one place.
- **Decompose by responsibility, not execution order** (avoid temporal decomposition):
  structure around knowledge, not around the order operations happen to run in. "Read, then
  modify, then write" as three modules usually leaks the format into all three.
- Expose the *general* capability, hide the *specific* policy. Don't add a config parameter
  the caller must understand when a sensible internal decision would do.

## Layers and abstraction

- **Different layer, different abstraction.** Adjacent layers that share the same
  abstraction are a smell.
- **Each method should add abstraction.** A method that only forwards to another with the
  same signature (a pass-through method) adds interface without value — add value or let the
  caller go direct.
- **Thread context, not pass-through variables.** When a value would otherwise be threaded
  through many layers just to reach the bottom, introduce a context object or rethink the
  boundary.
- **Pull complexity downward.** It is better for the *module's* implementation to be complex
  than for its interface — and every caller — to be. Suffer once, inside, so users don't.

## General-purpose interfaces

Make interfaces somewhat more general-purpose than the immediate need. A general interface
is usually simpler *and* more reusable than a special-purpose one. Ask: "what is the
simplest interface that covers my current needs without baking in today's specific use?"

## Define errors out of existence

The best way to handle an error is to design it away.

- Reduce the number of places that must handle errors. Prefer APIs whose normal path also
  covers the edge (e.g. `unset` on a missing key is a no-op, not an exception).
- Use the language's result/exception conventions from the language rules; here the design
  rule is: **minimize the number of exceptional cases the caller must reason about.**

## Naming

Names are the densest documentation in the code. A good name is **precise, consistent,
and obvious**.

- If you cannot find a precise name, the design is probably muddled — the thing does too
  many things. Treat naming difficulty as a design signal.
- Name length should scale with scope: loop indices can be `i`; a module-level export
  cannot.
- Use the same word for the same concept everywhere, and never the same word for two
  concepts.

## Comments

Comments exist to capture what the code cannot: the *why*, the abstraction, and the
non-obvious. They are part of the design, not an afterthought.

- Comment the **interface** (what a caller needs to know to use it) separately from the
  **implementation** (why it works this way). The interface comment is the abstraction.
- Write the interface comment *first*, before the body — if it's hard to write, the
  interface is too complex (design feedback, for free).
- Never write a comment that just restates the code. Document the things that are *not*
  obvious from reading it.
- Comments describe *why*, not *what*. The code already says what.

## Tactical vs strategic

Program **strategically**, not tactically. The goal is a good design, not just working
code. Invest a little extra continuously (better structure, better names, a comment) rather
than taking shortcuts that compound. There are no "tactical tornado" exceptions in this
codebase.

## Red flags — stop and reconsider if you see these

- **Shallow module** — interface nearly as complex as the implementation.
- **Information leakage** — the same decision encoded in two places.
- **Temporal decomposition** — modules mirror execution order, not responsibilities.
- **Overexposure** — using the common case forces the caller to learn rare options.
- **Pass-through method / variable** — added layer carries no new abstraction.
- **Repetition** — the same snippet appears more than twice.
- **Special-general mixture** — special-purpose code embedded in a general-purpose mechanism.
- **Conjoined methods** — two pieces only understandable by reading both back-to-back.
- **Comment repeats code** — or, you can't write a comment without restating the body.
- **Hard to name / hard to describe** — the unit's responsibilities aren't clean.

## Testability is a design property

Code that is hard to test through its public interface is badly factored. Design modules so
their behavior is observable at the boundary without reaching inside. See `tdd.md` — tests
exercise public interfaces, never implementation details.
