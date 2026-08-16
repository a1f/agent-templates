---
paths: "**/*.py", "**/*.ts", "**/*.tsx", "**/*.rs", "**/*.go", "**/*.java", "**/*.cpp", "**/*.cc", "**/*.h", "**/*.hpp"
---

# Comment Rules

What a comment may say, how long it may be, and where the rest of the reasoning goes.
`design-principles.md` says a comment carries what the code cannot. This file says how much,
because "carry the why" read alone produces a paragraph on every line. Adapted from Ousterhout
ch. 13, the Google style guides, and Anthropic's own coder guidance: state a constraint the
code cannot show, never why your change is correct. The coder writes to this file; the
`comment-reviewer` agent scores against it.

## The two comments always allowed

1. **The file comment.** Only when the file name does not say what the file is for. One or
   two sentences at the top: what lives here, and why it is its own file.
2. **The interface comment** on a public function, class, or module (the docstring, JSDoc,
   `///`). One sentence: what the caller gets, and why it exists when the name does not say.
   A second sentence only for a contract the signature and names cannot carry: a precondition,
   an error the body raises and the caller must handle, an ordering guarantee, a side effect.

Every other comment is an **inline comment**, and an inline comment must earn its place.

## The test for an inline comment

Ask: **would a competent reader change this line wrongly without the comment?** If yes, write
one line that names the constraint. If no, write nothing. If a function needs a comment above
each block, extract the blocks (the phased function in `design-principles.md`) instead of
narrating them.

## Where the reasoning goes

| The reader wants to know | It lives in |
|---|---|
| what the function does for the caller | the interface comment, one sentence |
| the one non-obvious constraint on a line | an inline comment, one line |
| why this design and not another; the failure modes weighed; the bug that taught us | the commit message, the PR body, or a design doc |
| what the code must do | the test |
| how the code does it | the code |

## Size

- An interface comment is one sentence; three lines at most. A section the language rule
  requires (`# Errors`/`# Panics`/`# Safety` in `rust.md`, Doxygen tags in `cpp.md`) sits below
  the sentence and outside the cap, one line per condition.
- An inline comment is one line; two at most.
- Sentence caps from `english.md` apply: 25 words.
- There is no ration. A comment that passes the test is never slop, and a file with many
  such comments is fine. The caps bound each comment, not their number.

## Slop shapes — delete on sight

| Shape | What it looks like | Do this |
|---|---|---|
| **essay** | a docstring that walks through every failure mode or every decision, or a comment that illustrates a constraint with the concrete case that taught it | cut to the one-sentence contract or the one-line constraint; the story goes to the PR body |
| **defense** | a comment that argues the code is right, as a reply to a review that already happened | cut the argument; if a constraint hides in it (a security assumption, an ordering, an invariant), keep that as the one line |
| **echo** | an inline comment that repeats the docstring, the commit message, or the test name | delete the copy |
| **breadcrumb** | written about the change or the task, not the code: "added for", "used by X", "now", "previously", "per issue #123", "for a later slice" | delete; the PR body carries it |
| **alternative** | describes what the code does *not* do ("a Mount would instead …") | one clause naming the choice, or delete |
| **restatement** | says what the next line plainly says | delete |
| **emphasis** | CAPS, *italics*, "hence", "which is exactly how" | delete the emphasis; keep the fact if there is one |
| **stale** | disagrees with the code beside it | fix or delete in the same change |
| **missing** | a public interface with a non-obvious contract and no interface comment | add the one sentence |

## When you add, fix, or refactor

- A slice adds at most the comment its own line needs. Never write the reason for a fix
  round into the code; the PR body carries it.
- A refactor or a fix round deletes every comment the change made stale and every echo the
  change exposed. Leaving a stale comment is a defect, not a nit.
- Match the comment density of the file you touch, unless that density breaks this file.

## Before and after

Real output from a coder that read "carry the why" alone (twelve comment lines over five of code):

```python
# BAD — an essay above five lines of code
def serve_spa(*, app: FastAPI) -> None:
    """Serve the built frontend from the same origin as the API, so one image answers
    both: the UI at `/`, the API under its prefix.

    Where the build lives is a deployment fact (`SPA_DIR`), not a caller's choice. A
    run with no build at all — a backend-only dev server, an image built without the
    web stage — is not an error: the app then serves the API alone and `/` is a 404.
    """
    build: Path = Path(os.environ.get(SPA_DIR_ENV, DEFAULT_SPA_DIR))
    if not (build / SPA_INDEX_FILE).is_file():
        return
    # The router's default answers only where NO route matched, which makes the SPA a
    # fallback rather than a mount at "/": a route registered after this call still
    # wins, so there is no ordering trap for a later slice to fall into. A Mount("/")
    # would instead match every path — including one registered after it — and swallow
    # it into the SPA.
    app.router.default = _SpaFallback(directory=build, router_default=app.router.default)
```

```python
# GOOD — the contract in one sentence, the one non-obvious choice in one line
def serve_spa(*, app: FastAPI) -> None:
    """Serve the built frontend from the API's origin; with no build, serve the API alone."""
    build: Path = Path(os.environ.get(SPA_DIR_ENV, DEFAULT_SPA_DIR))
    if not (build / SPA_INDEX_FILE).is_file():
        return
    # Router default, not Mount("/"): a route registered later still wins.
    app.router.default = _SpaFallback(directory=build, router_default=app.router.default)
```

The ten cut lines were true. They belong in the PR body, where the reader who wants the
design story goes to find it.
