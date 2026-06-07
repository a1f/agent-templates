---
paths: ["**/*.rs", "**/Cargo.toml"]
---

# Rust Rules

Target Edition 2024 (Rust 1.85+). Pin `rust-version` in `Cargo.toml`, commit `Cargo.lock`, and
keep modern idioms with strict linting throughout. Follow the
[Rust API Guidelines](https://rust-lang.github.io/api-guidelines/) and the official
[Rust Style Guide](https://doc.rust-lang.org/style-guide/) — both are what `rustfmt`/`clippy`
encode.

## Tooling

- **Formatter:** rustfmt via `cargo fmt`. The official style is non-negotiable: 4-space indent,
  100-column width, block (not visual) indent, trailing commas in multi-line lists, line comments
  (`//`) over block, one combined `#[derive(...)]` per item. Put any overrides in `rustfmt.toml`.
- **Linter:** clippy. `cargo clippy --all-targets --all-features -- -D warnings` is clean before
  every commit. **Fix warnings, never silence them** — reach for `#[allow(...)]` only with a
  comment justifying it (lint levels live in `[workspace.lints]` — see Workspace Lints).
- **Async runtime:** Tokio (async-std is discontinued).
- **Error handling:** thiserror (libraries) + anyhow (applications); eyre is an acceptable
  alternative for rich application error reports.
- **Tests:** `cargo test` (unit + integration + doc tests). Use **cargo-nextest** as the local
  runner (faster parallelism, better output) — it does **not** run doc tests, so keep
  `cargo test --doc` alongside it. **proptest** for property-based tests (per-value shrinking).
- **CI checks:** `cargo doc --no-deps`, `cargo audit`, `cargo deny` (known vulnerabilities + license violations).

## Naming

Follow the Rust API Guidelines casing: `UpperCamelCase` for types/traits/enum variants,
`snake_case` for functions/methods/variables/modules, `SCREAMING_SNAKE_CASE` for consts/statics.

- Names say what they mean (`is_in(haystack, needle)`, not `is_in(a, b)`); keep a consistent word
  order (`verb_noun`); omit the type from the name unless it disambiguates.
- Generic parameters are short, conventionally a single uppercase letter (`T`, `K`, `V`).
- Lifetimes get short descriptive lowercase names (`'heap`); use `'a` only for trivial single-use
  lifetimes, and never numbered lifetimes.
- Suffix error types with `Error`; bind pattern variables to the source name or its first letter
  (`if let Some(response) = event.response`), not an inconsistent rename.

## Error Handling

Use `Result<T, E>` in all public APIs. **Never panic in library code** (assertions guarding
genuine invariants excepted). No `unwrap()`/`expect()` on production paths.

- **Libraries:** define concrete error enums with `#[derive(thiserror::Error)]` so callers can
  match variants. Add a crate-level `type Result<T> = std::result::Result<T, Error>;` alias and
  `From` impls so `?` converts cleanly.
- **Applications:** use `anyhow::Result` (or `eyre::Result`) for top-level propagation.
- Propagate with `?`; add context (`.context("failed to open config")?`). Discard an error
  deliberately with `.ok()`, never a `|_| ()` closure.
- Tests must exercise the error paths, not just the happy path.

## Ownership and Idioms

- **Borrow over clone**, and avoid redundant clones on hot paths. Pass `&T`; take `T` by value
  only for `Copy` types or when you genuinely consume it.
- Bind a value, then borrow the binding — `let foo = make(); use(&foo);`, not `let foo = &make();`.
  Start a `let` with `&` only when indexing or slicing.
- **Iterators over manual loops:** `items.iter().filter(..).map(..).collect()` reads top-to-bottom
  and optimizes as zero-cost abstraction; prefer `.collect()` to `FromIterator::from_iter`.
- Allocate late: `Vec::with_capacity(n)` when the size is known, `Vec::new()` for an empty
  collection.
- Use `Self` inside impls to refer to the type; never shadow a type name, and keep value shadowing
  to one level or a single type-changing conversion. Lowercase hex literals (`0xab5c`).

## Generics and Dispatch

- Prefer **static dispatch** (`impl Trait`, `<T: Trait>`); reach for `dyn Trait` only when runtime
  polymorphism is actually required.
- Move bounds to a `where` clause once they need a compound constraint or would push the
  angle-bracket header past ~30 characters.
- Every generic parameter must be used in the signature — an unused one signals a modeling mistake.

## Imports

Three groups, blank-line separated, in order: `std`/`core`/`alloc`; third-party crates; local
(`crate`/`super`/`self`).

- No glob imports (`use foo::*`) except `use super::*;` inside a `#[cfg(test)]` module. Don't glob
  enum variants — rename locally (`use SomeLongEnum as Se;`) if needed.
- Group same-path imports with nested braces (`use a::b::{C, D};`).

The std/external/local grouping and same-path brace-merging are produced only by the *unstable*
rustfmt options `group_imports`/`imports_granularity`. Stable `cargo fmt` (the gate) only sorts within
existing groups, so on stable these two are reviewer-enforced conventions; to automate them, set
`group_imports = "StdExternalCrate"` and `imports_granularity = "Crate"` in `rustfmt.toml` and run
`cargo +nightly fmt`.

## Documentation

Doc comments (`///`) required on all public items, written as complete sentences. Include these
sections where applicable:

- `# Errors` — when the function returns `Result`, list the error conditions.
- `# Panics` — document any conditions under which the function panics.
- `# Safety` — required on every `unsafe fn`; document the invariants the caller must uphold.

Apply `#[must_use]` on constructors, builders, and fallible operations whose return value should
not be silently dropped (the `must_use_candidate` clippy lint catches misses). Comments explain
*why*, not *what*; promote a lingering `TODO` into a tracked issue rather than leaving it in code.

## Unsafe Discipline

- Set `unsafe_code = "deny"` in `[workspace.lints.rust]`; use `#![forbid(unsafe_code)]` at the
  crate root for crates that must stay pure-safe.
- Every `unsafe` block carries a `// SAFETY:` comment explaining why the invariants hold.
- Minimize the unsafe surface: wrap it in safe abstractions with documented preconditions.

## Workspace Lints

Configure lints via `[workspace.lints]` in the workspace `Cargo.toml`; member crates inherit with
`[lints] workspace = true`. Do not use inline `#![allow(...)]`/`#![warn(...)]` at the crate level.

```toml
[workspace.lints.rust]
unsafe_code = "deny"
missing_docs = "warn"
unreachable_pub = "warn"

[workspace.lints.clippy]
# Cherry-pick from pedantic — do NOT enable the whole pedantic group
doc_markdown = "warn"
manual_let_else = "warn"
match_same_arms = "warn"
redundant_closure_for_method_calls = "warn"
semicolon_if_nothing_returned = "warn"
must_use_candidate = "warn"
needless_pass_by_value = "warn"
uninlined_format_args = "warn"
```

## Async

Native `async fn` in traits is stable — use it directly. But it cannot express a `Send` bound on the
returned future, so a future obtained through a generic or `dyn` bound will not satisfy `tokio::spawn`
on the multithreaded runtime; when you must spawn the result, return `-> impl Future<Output = …> +
Send` explicitly, annotate the trait with `#[trait_variant::make(Send)]`, or fall back to
`#[async_trait]` (which boxes a `Send` future). Reach for `#[async_trait]` for dyn-compatibility **or**
when you need that `Send` bound for spawning.

- `tokio::select!` to multiplex futures; `tokio::sync::mpsc` for async channels.
- Offload CPU-bound or blocking work to `tokio::task::spawn_blocking`; never block the async
  executor with synchronous I/O.

## Serde

- `#[serde(rename_all = "camelCase")]` for JSON API types.
- `#[serde(deny_unknown_fields)]` on configuration structs to catch typos — but **not** combined
  with `#[serde(flatten)]` (they conflict and produce confusing errors).

## Project Structure

- Organize modules by **capability/domain**, not by language feature — no `types.rs` / `impl.rs`
  split. Keep a struct and its `impl` blocks in the same file. Apply the "could this be a separate
  crate?" test to find module boundaries.
- Workspace: a virtual manifest (no `[package]`, only `[workspace]`) with a flat `crates/` layout
  (`core/`, `api/`, `cli/`). Declare shared deps in `[workspace.dependencies]` and reference them
  with `dep.workspace = true` so versions stay consistent.
- **No `println!`/`eprintln!`/`dbg!` in library code** — emit structured events through `tracing`
  (or `log`); binaries initialize the subscriber, libraries only emit.

## Testing

Test discipline (red → green → refactor, behavior through the public interface) lives in `tdd.md`.
Rust specifics:

- Unit tests in a `#[cfg(test)] mod tests { use super::*; }` block beside the code; integration
  tests in `tests/`; doc tests double as living, compiled usage examples.
- **proptest** for property-based tests of pure functions; prefer a property over a handful of
  examples when the rule is general.
- The default gate runs `cargo test --all-features` (swap in `cargo nextest run` for projects that
  adopt it, keeping doc tests). Configure features, lint levels, and `rust-version` in committed
  config, not on the gate command line.
