---
paths: "**/*.py", "**/*.ts", "**/*.tsx", "**/*.rs", "**/*.go", "**/*.java", "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp"
---

# Design Principles

Language-agnostic rules for structure, abstraction, and readability. Language rules
(`python.md`, `typescript.md`, `rust.md`, …) govern *syntax and idiom*; this file governs *design*.
Based on Ousterhout's *A Philosophy of Software Design*. Apply the relevant rules to every
change, but scale the effort to the mode: GREEN stays minimal; REFACTOR is where structural
improvement usually belongs.

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

```python
# SHALLOW — interface as complex as the body; caller learns 3 knobs to save nothing
def write(path, data, *, mkdirs, encoding, atomic): ...   # caller still owns every decision

# DEEP — one-word interface hiding mkdirs/atomic-rename/encoding decisions
def save(path: Path, data: str) -> None: ...              # the hard parts live inside
```

## Information hiding

Each module should encapsulate a few design decisions that nothing outside it depends on.
That is what makes interfaces simple and change local.

- **Keep each design decision in one place** (no information leakage): a file format, a
  protocol detail, or a default should live in a single module. If changing one forces a
  change in another, the knowledge leaked — pull it into one place.
- **Decompose by responsibility, not execution order** (avoid temporal decomposition):
  structure around knowledge, not around the order operations happen to run in. "Read, then
  modify, then write" as three modules usually leaks the format into all three.

```python
# TEMPORAL — three modules mirror the steps; each must know the file format → leaked 3×
text = read_yaml(path); patched = bump_version(text); write_yaml(path, patched)

# RESPONSIBILITY — one module owns the format; callers never see it
config = ConfigFile(path); config.bump_version(); config.save()
```
- Expose the *general* capability, hide the *specific* policy. Don't add a config parameter
  the caller must understand when a sensible internal decision would do.

## Better together or apart

A module should have **one job** and do it fully. Combine two pieces of functionality into one
module only when that genuinely reduces complexity; otherwise keep them apart.

- **One concern per module.** A datastore and a cache are two concerns: expose a *store*
  interface and hide caching as an implementation detail *inside* it, or keep them as separate
  modules — never ship a `StoreAndCache` that does both. If the name needs an "and", or you
  can't state the job in one phrase, split it.

```python
# BAD — two concerns in one interface; callers must know the cache exists
class StoreAndCache:
    def get(self, k): ...
    def cache_get(self, k): ...
    def invalidate(self, k): ...

# GOOD — one Store interface; caching is a hidden implementation decision
class Store:
    def get(self, k): ...   # may consult a private cache inside; callers never know
```
- **Bring together** when the pieces share information, when one interface is simpler than two
  (callers learn one abstraction), or when it removes duplication or a shallow go-between.
- **Keep apart** when the pieces are used independently, when one is general-purpose and the
  other special-purpose, or when bundling forces callers to learn things they don't need.
- The test is complexity, not line count: merge if the whole is simpler than the parts; split
  if the parts are simpler than the whole.

## Layers and abstraction

- **Different layer, different abstraction.** Adjacent layers that share the same
  abstraction are a smell.
- **Each method should add abstraction.** A method that only forwards to another with the
  same signature (a pass-through method) adds interface without value — add value or let the
  caller go direct.

```python
def get_user(self, uid):           # BAD — pure forwarder, same signature, no new abstraction
    return self._repo.get_user(uid)

def get_user(self, uid):           # OK — earns the layer: adds caching + a domain error
    hit = self._cache.get(uid)
    return hit if hit is not None else self._fetch_or_raise(uid)
```
- **Thread context, not pass-through variables.** When a value would otherwise be threaded
  through many layers just to reach the bottom, introduce a context object or rethink the
  boundary.
- **Pull complexity downward.** It is better for the *module's* implementation to be complex
  than for its interface — and every caller — to be. Suffer once, inside, so users don't.

## General-purpose interfaces

Do **not** add public options before a behavior requires them. During GREEN, implement only the
current slice. Once two real slices need the same capability, extract the smallest interface
that covers both without encoding one caller's special policy. General-purpose means "less
policy leaked to callers," not "more knobs just in case."

## Avoid flag parameters

A boolean argument that selects between two behaviors is a sign of a module doing two jobs. The
caller writes `render(doc, true)` and cannot tell what `true` means; the body branches on a flag
instead of presenting one clear abstraction.

- Split the behaviors into two named functions (`renderDraft` / `renderFinal`) rather than one
  function with a mode switch — the names document the intent the flag hid.

```python
def export(data, *, as_csv):        # BAD — caller passes a bare bool; body forks on it
    if as_csv: ...
    else: ...

def export_csv(data): ...           # GOOD — two clear abstractions, no flag to decode
def export_json(data): ...
```
- Keep a parameter only when callers genuinely vary it along a continuum, not when it toggles
  between two code paths that share little.

## Side effects and boundaries

Push I/O and mutation to the edges; keep the core a set of pure functions that map inputs to
outputs. Pure logic is the part you can read, test, and reuse without standing up the world.

- **Functional core, imperative shell.** Concentrate side effects (network, disk, clock,
  randomness, global state) in thin boundary layers and keep decision-making logic pure. A
  function that both computes *and* persists is harder to test and reuse than the two kept apart.
- **Parse untrusted input at the boundary, once.** Convert external data (request bodies, env
  vars, file contents, API responses) into trusted domain types at the edge — parse, don't
  validate — so the interior assumes well-formed values instead of re-checking them. Never trust
  external input deeper than the boundary that admitted it.

## Define errors out of existence

The best way to handle an error is to design it away.

- Reduce the number of places that must handle errors. Prefer APIs whose normal path also
  covers the edge (e.g. `unset` on a missing key is a no-op, not an exception).

```python
def unset(self, key):              # BAD — every caller must wrap in try/except
    if key not in self._d: raise KeyError(key)
    del self._d[key]

def unset(self, key):              # GOOD — missing key is a no-op; the error case vanishes
    self._d.pop(key, None)
```
- Use the language's result/exception conventions from the language rules.

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
- **The interface comment is a complete contract when the signature and names are not enough.**
  Prefer concise language-rule docstrings, but include any non-obvious preconditions, errors,
  side effects, or ordering guarantees a caller needs. Do not duplicate obvious parameter or
  return types just to be exhaustive.

## Consistency

Do similar things in similar ways. Consistency lowers cognitive load and unknown-unknowns: once
a reader learns a pattern, they can rely on it holding everywhere.

- **Follow the conventions already in the codebase** — naming schemes, file and module layout,
  error handling, how a common task is wired. A change that invents a new way to do an existing
  thing adds a pattern every future reader must learn.
- Keep **parallel cases parallel**: sibling handlers, similar endpoints, and repeated shapes
  should read the same way, so understanding one means understanding the rest.
- Diverge from an established pattern only when the pattern is wrong — then fix the pattern,
  don't add a competing one beside it.

## Code should be obvious

Code is read far more than it is written. Aim for code whose behavior a reader grasps quickly
and correctly, without surprises. **Non-obvious code is a defect**, even when it is correct.

- If a reader must pause to work out what a piece of code does, or could reasonably read it
  wrong, that is a problem — fix it with clearer names and structure first.
- When the *why* still isn't obvious from well-named code, that is what a comment is for (see
  Comments) — but reach for structure before commentary.
- Avoid surprises: don't give something a name or signature that implies behavior it lacks, and
  don't hide a side effect where a reader won't expect it. The obvious reading should be correct.

## Tactical vs strategic

Program **strategically**, not tactically. The goal is a good design, not just working
code. Invest a little extra continuously (better structure, better names, a comment) rather
than taking shortcuts that compound. There are no "tactical tornado" exceptions in this
codebase.

## Design it twice

Your first idea for a non-trivial design is rarely your best. Before committing, sketch **two
genuinely different approaches** and compare them — the comparison is what reveals the better
design, and sometimes a third that beats both.

- Spend this effort in proportion to the decision: a throwaway helper doesn't need it; a module
  boundary, a public interface, or a data shape does (scale to the mode, as the intro says).
- Compare on the criteria that matter here — which interface is simpler and deeper, which hides
  more, which has fewer special cases — not which is faster to type.

## Red flags — stop and reconsider if you see these

- **Shallow module** — interface nearly as complex as the implementation.
- **Information leakage** — the same decision encoded in two places.
- **Temporal decomposition** — modules mirror execution order, not responsibilities.
- **Overexposure** — using the common case forces the caller to learn rare options.
- **Pass-through method / variable** — added layer carries no new abstraction.
- **Repetition** — the same snippet appears more than twice.
- **Special-general mixture** — special-purpose code embedded in a general-purpose mechanism.
- **Multi-concern module** — one module owns two jobs that don't share information; the name needs an "and".
- **Flag parameter** — a boolean argument selects between two behaviors; split the function instead.
- **Scattered side effects** — I/O or mutation interleaved through logic that could be a pure core.
- **Re-validated input** — the same external value checked in many places instead of parsed once at the boundary.
- **Conjoined methods** — two pieces only understandable by reading both back-to-back.
- **Comment repeats code** — or, you can't write a comment without restating the body.
- **Hard to name / hard to describe** — the unit's responsibilities aren't clean.
- **Inconsistency** — a new pattern for something the codebase already does one established way.
- **Non-obvious code** — a reader must stop and puzzle out what it does, or could read it wrong.

## Testability is a design property

Code that is hard to test through its public interface is badly factored — design modules so
behavior is observable at the boundary without reaching inside (see `tdd.md`).
