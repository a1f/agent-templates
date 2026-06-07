---
paths: "**/*_test.py", "**/test_*.py", "**/*.test.ts", "**/*.test.tsx", "**/*.spec.ts", "**/tests/**"
---

# TDD Rules

How tests get written in this codebase: red → green → refactor, in vertical slices.
Adapted from the test-first discipline of *Growing Object-Oriented Software* and Matt
Pocock's TDD skill. The `coder` and `tdd-runner` agents follow this; the `architect`
enforces the loop.

## Core principle

**Tests verify behavior through public interfaces, never implementation details.**

A good test reads like a specification of what the system does for a user. It survives any
internal refactor that preserves behavior. The defining smell of a bad test: it breaks when
you refactor even though behavior did not change.

- Do **not** mock internal collaborators, test private methods, or assert on internal state.
- Mock only true external boundaries (network, clock, filesystem, third-party APIs).
- If a behavior is only reachable by poking internals, the design is wrong — fix the design,
  not the test (see `design-principles.md`).
- Write the **fewest** tests that pin the behavior. Prefer one test through the real public
  interface over many that re-check the same path from different angles. Never add a test solely
  to cover a line or branch, and never test a dormant or unreachable path — coverage is a
  diagnostic, not a target. A suite that grows faster than the behavior it describes is slop.

## Anti-pattern: horizontal slices

Never write all the tests up front and then all the implementation. Tests written against
imagined behavior assert the shape of data structures rather than user-facing capability,
and go stale the moment the implementation teaches you something. **Always vertical slices:
one test → one implementation → repeat (tracer bullets).**

## The loop

For each behavior, in order:

1. **RED** — Write exactly one test for one behavior. Run it. Watch it fail **for the right
   reason** — an assertion failure, or a missing symbol the GREEN step will add that exactly
   matches the target public interface, not an import typo, syntax error, or fixture mistake. A
   test that has never failed proves nothing.
2. **GREEN** — Write the *minimum* code to make that test pass. No speculative features, no
   handling of cases no test demands yet.
3. **REFACTOR** — Only once green. Remove duplication, improve names, deepen modules per
   `design-principles.md`. Re-run tests; they must stay green. **Never refactor while red.**

## Planning a change (before the first RED)

- Confirm the public interface from the task spec.
- List the **behaviors** to cover (user-facing outcomes), not implementation steps.
- Order them so each slice is a thin end-to-end path.
- The task spec must include explicit acceptance criteria or a behavior list. If it does not,
  stop for re-scope. If it does, proceed and log the chosen behavior list; ask the human only
  when multiple materially different interfaces or behavior lists are plausible.

## When TDD is mandatory

TDD is required for any change with **behavior or logic**: new functions, branching,
parsing, state changes, and bug fixes.

It may be **skipped** only for changes with no behavior to assert: pure config, dependency
bumps, docs, comments, formatting, and mechanical renames. When skipped, the `architect`
logs the skip with a reason in the run log. When in doubt, do TDD.

A bug fix **always** starts with a failing test that reproduces the bug.

## Per-cycle checklist

- [ ] Test names a behavior, not a method (`returns_empty_cart_total_as_zero`, not `test_total`).
- [ ] Test uses only the public interface.
- [ ] Test was seen to fail for the right reason before any production code.
- [ ] Production code is minimal for the current test.
- [ ] No speculative feature was added.
- [ ] After refactor, all tests still green.

## Tooling

- Prefer a **property-based** test (hypothesis / proptest) over a handful of examples when the rule
  is general, and measure **branch** coverage, not just line.
- The test runner, async support, and where tests live are language-specific — see the language
  rule (`python.md`, `typescript.md`, `rust.md`) for the runner and layout.

## What a good test looks like

```python
# GOOD — behavior through the public interface
def test_discount_applies_to_subtotal():
    cart = Cart(items=[Item(price=100), Item(price=50)])
    assert cart.total(discount=Percent(10)) == 135

# BAD — couples to implementation; breaks on harmless refactor
def test_discount_calls_internal_multiplier():
    cart = Cart(items=[Item(price=100)])
    cart._apply_discount = Mock()
    cart.total(discount=Percent(10))
    cart._apply_discount.assert_called_once()
```

```typescript
// GOOD (vitest) — same lesson: assert the public result, not an internal call
test("discount applies to subtotal", () => {
  const cart = new Cart([item(100), item(50)]);
  expect(cart.total({ discount: percent(10) })).toBe(135);
});
```

```rust
// GOOD (cargo test) — same lesson: assert the public result, not an internal call
#[test]
fn discount_applies_to_subtotal() {
    let cart = Cart::new(vec![item(100), item(50)]);
    assert_eq!(cart.total(Percent(10)), Money(135));
}
```
