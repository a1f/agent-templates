# Research: Rust Best Practices (2025-2026)

## Target: Edition 2024 (Rust 1.85+)

Edition 2024 is the most comprehensive edition to date. Key changes: `unsafe_op_in_unsafe_fn` warning by default, `unsafe extern` blocks required, async closures, let chains, `Future`/`IntoFuture` in prelude.

## Tooling Decisions

| Tool | Choice | Rationale |
|------|--------|-----------|
| Async runtime | **Tokio** | async-std discontinued March 2025. Tokio is the only mainstream choice. |
| Error handling | **thiserror + anyhow** | Industry standard. thiserror for libraries, anyhow for applications. |
| Property testing | **proptest** | Better than quickcheck (per-value shrinking, composable strategies). |
| Test runner | **cargo-nextest** | Faster parallelism, better output. Becoming CI standard. |
| Snapshot testing | **insta** | Golden-file testing for complex outputs. |
| Mocking | **mockall** | Mock generation for traits. |

## Rules: Key Changes from Original Design

### CHANGED:
- ~~cargo clippy before commit~~ → **cargo fmt + cargo clippy before commit, cargo doc --no-deps in CI**
- ~~thiserror/anyhow for errors~~ → Confirmed. Also mention eyre as alternative for rich error reports.

### ADDED:
1. **Edition 2024** — target in Cargo.toml. Specify `rust-version` field.
2. **async-std is dead** — use Tokio exclusively. Native `async fn` in traits is stable (no more `#[async_trait]` for most cases). Fall back to `#[async_trait]` only for dyn-compatible traits.
3. **Workspace lints** — configure via `[workspace.lints]` in Cargo.toml, not inline attributes:
   ```toml
   [workspace.lints.rust]
   unsafe_code = "deny"
   missing_docs = "warn"
   unreachable_pub = "warn"

   [workspace.lints.clippy]
   doc_markdown = "warn"
   manual_let_else = "warn"
   # cherry-pick from pedantic, don't enable whole group
   ```
4. **Cherry-pick from pedantic** — do NOT enable `clippy::pedantic` group. Cherry-pick: `doc_markdown`, `manual_let_else`, `match_same_arms`, `redundant_closure_for_method_calls`, `semicolon_if_nothing_returned`, `must_use_candidate`, `needless_pass_by_value`, `uninlined_format_args`.
5. **Unsafe discipline** — `// SAFETY:` comments mandatory on all unsafe blocks. Use `#[forbid(unsafe_code)]` on pure-safe crates.
6. **No `println!` in library code** — use `log`/`tracing` instead.
7. **Serde patterns** — `rename_all = "camelCase"` for JSON APIs, `deny_unknown_fields` for configs, avoid `deny_unknown_fields` + `flatten` combination.
8. **Workspace structure** — virtual manifest, flat `crates/` layout, shared `[workspace.dependencies]`.
9. **Supply chain security** — `cargo audit` + `cargo deny` in CI.
10. **Testing** — proptest for property-based, cargo-nextest for CI, insta for snapshots.

## What Major Projects Use

| Project | unsafe_code | Lints location | Key practice |
|---------|-------------|---------------|-------------|
| Bevy | deny | `[workspace.lints]` | Custom `bevy_lint`, `allow_attributes_without_reason` |
| Axum | **forbid** | `[workspace.lints]` | Strictest — cannot override with `#[allow]` |
| Both | — | Cherry-pick ~15-35 clippy lints from pedantic | Allow `type_complexity`, `too_many_arguments` |

## Sources

- [Rust 1.85.0 + Edition 2024](https://blog.rust-lang.org/2025/02/20/Rust-1.85.0/)
- [async-std discontinuation](https://corrode.dev/blog/async/)
- [Clippy documentation](https://doc.rust-lang.org/stable/clippy/lints.html)
- [Bevy Cargo.toml](https://github.com/bevyengine/bevy/blob/main/Cargo.toml)
- [Axum Cargo.toml](https://github.com/tokio-rs/axum/blob/main/Cargo.toml)
- [Rust Security Best Practices 2025](https://corgea.com/Learn/rust-security-best-practices-2025)
