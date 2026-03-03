---
paths: "**/*.rs", "**/Cargo.toml"
---

# Rust Rules

Target Edition 2024 (Rust 1.85+). Specify `rust-version` in Cargo.toml. Use modern idioms and strict linting throughout.

## Tooling

- **Formatter/Linter:** Run `cargo fmt` then `cargo clippy` before every commit
- **Async runtime:** Tokio (async-std is discontinued). Use `tokio::select!`, `tokio::sync::mpsc` for channels, `spawn_blocking` for CPU-bound work
- **Error handling:** thiserror (libraries) + anyhow (applications). eyre is an acceptable alternative for rich error reports
- **Property testing:** proptest (per-value shrinking, composable strategies)
- **Test runner:** cargo-nextest (faster parallelism, better output)
- **CI checks:** `cargo doc --no-deps`, `cargo audit`, `cargo deny`

## Error Handling

Use `Result<T, E>` in all public APIs. Never panic in library code.

- **Libraries:** Define error enums with `#[derive(thiserror::Error)]`. Expose concrete error types so callers can match variants.
- **Applications:** Use `anyhow::Result` (or `eyre::Result`) for top-level error propagation.
- Chain errors with context: `.context("failed to open config")?` or `.map_err(|e| ...)?`

## Documentation

Doc comments (`///`) required on all public items. Include these sections where applicable:

- `# Errors` — when the function returns `Result`, list the error conditions
- `# Panics` — document any conditions under which the function panics
- `# Safety` — required on all `unsafe fn`; document the invariants the caller must uphold

## `#[must_use]`

Apply `#[must_use]` on functions whose return value should not be silently discarded (constructors, builders, fallible operations). Prefer the `must_use_candidate` clippy lint to catch missed cases.

## Iterators Over Explicit Loops

Prefer iterator chains (`.iter()`, `.map()`, `.filter()`, `.collect()`) over explicit `for` loops with manual accumulation. Iterator chains are more composable, often optimize better, and express intent more clearly.

## Unsafe Discipline

- Set `unsafe_code = "deny"` in `[workspace.lints.rust]`
- Use `#[forbid(unsafe_code)]` at the crate root for crates that must remain pure-safe
- Every `unsafe` block requires a `// SAFETY:` comment explaining why the invariants are upheld
- Minimize unsafe surface area: wrap unsafe code in safe abstractions with well-documented preconditions

## Workspace Lints

Configure lints via `[workspace.lints]` in the workspace `Cargo.toml`. Do not use inline `#![allow(...)]` or `#![warn(...)]` attributes at the crate level. Each member crate inherits with `[lints] workspace = true`.

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

Native `async fn` in traits is stable — use it directly. Only fall back to `#[async_trait]` when the trait must be dyn-compatible (i.e., used as `dyn Trait`).

- Use `tokio::select!` for multiplexing futures
- Use `tokio::sync::mpsc` for async channels
- Offload CPU-intensive work to `tokio::task::spawn_blocking`
- Avoid mixing blocking I/O on the async executor; use `spawn_blocking` or dedicated threads

## Serde

- Use `#[serde(rename_all = "camelCase")]` for JSON API types
- Use `#[serde(deny_unknown_fields)]` for configuration structs to catch typos
- Do **not** combine `deny_unknown_fields` with `#[serde(flatten)]` — they conflict and produce confusing errors

## No `println!` in Library Code

Library crates must not use `println!`, `eprintln!`, or `dbg!`. Use the `log` or `tracing` crate for structured, level-filtered output. Application binaries initialize the subscriber/logger; libraries only emit events.

## Workspace Structure

Use a virtual manifest with a flat `crates/` layout:

```
Cargo.toml          # virtual manifest (no [package], only [workspace])
crates/
  core/
  api/
  cli/
```

Define shared dependencies in `[workspace.dependencies]` and reference them in member crates with `dep.workspace = true`. This ensures version consistency across the workspace.

## Supply Chain Security

Run `cargo audit` and `cargo deny` in CI to catch known vulnerabilities and license violations. Pin dependencies with `Cargo.lock` committed to version control (required for binaries, recommended for libraries during development).
