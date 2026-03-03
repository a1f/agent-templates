---
paths: "**/*.ts", "**/*.tsx", "**/package.json"
---

# TypeScript Rules

Target TypeScript 5.8+. Use strict mode, modern ESM, and current tooling throughout.

## Compiler Configuration

Use `module: "nodenext"` (Node.js) or `module: "esnext"` (bundled apps). Always enable strict mode plus additional flags:

```json
{
  "strict": true,
  "noUncheckedIndexedAccess": true,
  "exactOptionalPropertyTypes": true,
  "noPropertyAccessFromIndexSignature": true
}
```

No CommonJS for new code. All files use ESM (`import`/`export`).

## Tooling

- **Linter/Formatter:** Biome (preferred) or ESLint + Prettier. Biome is faster (Rust-based, single config) and covers ~75-85% of typescript-eslint rules. Fall back to ESLint + Prettier only when Biome lacks a required rule.
- **Package manager:** pnpm (strict deps -- no phantom dependencies, best disk efficiency)
- **Tests:** vitest (native TS/ESM support, 10x faster than Jest in watch mode)
- **Validation:** Zod (or Valibot for bundle-sensitive apps). Prefer Standard Schema v1 compliant validators.
- **Monorepo:** Turborepo for multi-package TypeScript repos

## No Enums

Never use TypeScript `enum`. Use `as const` objects with derived union types instead:

```typescript
const Status = { Active: "active", Inactive: "inactive" } as const;
type Status = (typeof Status)[keyof typeof Status];
```

Rationale: enums generate runtime IIFE code, increase bundle size, and conflict with the "erasable types" direction (Node's native TS support). `as const` objects produce natural union types with better tree-shaking.

## No Barrel Exports

Do not create `index.ts` barrel files that re-export from other modules. Import directly from the source file:

```typescript
// BAD
import { UserService } from "./services";

// GOOD
import { UserService } from "./services/user-service.ts";
```

Barrel files are acceptable only at package public API boundaries (the main `index.ts` of a published package). Removing barrels reduces build times by up to 75% and eliminates circular import issues.

## Type Safety

- **`unknown` over `any`:** When a dynamic type is needed, use `unknown` with type narrowing (type guards, `instanceof`, `typeof`, or Zod parsing). Never use `any` unless wrapping an untyped third-party API, and isolate it behind a typed wrapper.
- **`const` over `let`**, never `var`. Reassignment should be rare; prefer deriving new values.
- **Explicit return types** on exported functions and public methods. Inferred return types are fine for local/private functions.
- **Discriminated unions** for modeling state:

```typescript
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };
```

## Error Handling

Use result types for expected/recoverable errors. Use neverthrow or a custom discriminated union (shown above). Reserve `throw` for truly exceptional, unrecoverable situations (programmer errors, invariant violations).

```typescript
// neverthrow style
import { ok, err, Result } from "neverthrow";

function parseConfig(raw: string): Result<Config, ParseError> {
  // ...
  return ok(config);
}
```

## Project Structure

- Keep `package.json` `type: "module"` for ESM
- Place shared types in dedicated `types.ts` files
- Place constants in `constants.ts` using `as const`
- Co-locate tests next to source files (`foo.ts` / `foo.test.ts`) or in a parallel `__tests__/` directory
- Use path aliases sparingly; prefer relative imports within a package

## Functions and Parameters

- Prefer functions over classes unless state management or lifecycle is needed
- Use object parameters for functions with 3+ arguments:

```typescript
function createUser(opts: { name: string; email: string; role: Role }): User {
  // ...
}
```

- Use `readonly` on array and object parameters that should not be mutated
- Prefer `satisfies` over type assertions (`as`) to validate types without widening

## Async Patterns

- Always `await` promises; never leave floating promises (use `void` prefix if intentionally fire-and-forget)
- Use `AbortSignal` for cancellation
- Prefer `using` (explicit resource management) for cleanup when targeting environments that support it

## Documentation

Single-sentence JSDoc explaining WHY the function exists, not WHAT it does. Parameter types and return types are in the signature; do not duplicate them in JSDoc `@param`/`@returns` tags.
