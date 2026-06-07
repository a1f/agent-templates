---
paths: ["**/*.ts", "**/*.tsx", "**/package.json"]
---

# TypeScript Rules

Target TypeScript 5.8+. Use strict mode, modern ESM, and current tooling throughout.

## Compiler Configuration

Use `module: "nodenext"` (Node.js — it sets `moduleResolution` automatically) or, for bundled apps, `module: "preserve"` (TS 5.4+, which implies `moduleResolution: "bundler"`). If you instead use `module: "esnext"`, you must also set `moduleResolution: "bundler"` explicitly — alone it falls back to the legacy `classic` resolver, which cannot read package `exports` maps. Always enable strict mode plus additional flags:

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

- **Linter/Formatter:** Biome for the default v1 TypeScript gate. Repos using ESLint + Prettier
  must provide an explicit TypeScript gate override before running v1.
- **Package manager:** pnpm (strict deps — no phantom dependencies)
- **Tests:** vitest (native TS/ESM support) + @vitest/coverage-v8 (branch coverage)
- **Validation:** Zod (or Valibot for bundle-sensitive apps). Prefer Standard Schema v1 compliant validators.
- **Monorepo:** Turborepo for multi-package TypeScript repos

## No Enums

Never use TypeScript `enum`. Use `as const` objects with derived union types instead:

```typescript
const Status = { Active: "active", Inactive: "inactive" } as const;
type Status = (typeof Status)[keyof typeof Status];
```

Rationale: enums emit runtime helper code and conflict with erasable-types (Node's native TS).
`as const` keeps runtime values as plain objects only when you actually need values, and derived
union types erase cleanly when you only need types.

## No Barrel Exports

Do not create `index.ts` barrel files that re-export from other modules. Import directly from the source file:

```typescript
// BAD
import { UserService } from "./services";

// GOOD
import { UserService } from "./services/user-service.ts";
```

Barrel files are acceptable only at package public API boundaries (the main `index.ts` of a published package). Removing barrels speeds builds and avoids circular imports.

## Type Safety

- **`unknown` over `any`:** When a dynamic type is needed, use `unknown` with type narrowing (type guards, `instanceof`, `typeof`, or Zod parsing). Never use `any`. If a third-party API lacks types and no `@types/` package exists, write a `.d.ts` declaration file instead.
- **`const` over `let`**, never `var`. Reassignment should be rare; prefer deriving new values.
- **Explicit return types** on exported functions and public methods. Inferred return types are fine for local/private functions.
- **Discriminated unions** for modeling state:

```typescript
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };
```

- **Exhaustiveness checking:** in every `switch` over a discriminated union, assign the
  default case to a `never` binding so adding a variant without handling it fails to compile:

```typescript
function area(s: Shape): number {
  switch (s.kind) {
    case "circle": return Math.PI * s.r ** 2;
    case "square": return s.side ** 2;
    default: { const _exhaustive: never = s; return _exhaustive; }
  }
}
```

- **Derive types with built-in utility types** (`Partial`, `Pick`, `Omit`, `Readonly`,
  `Record`, `ReturnType`, `Awaited`) instead of hand-maintaining parallel shapes that drift
  from their source of truth.
- **Every generic parameter must be used.** A type parameter that never appears in the
  parameters or return type breaks inference and signals a modeling mistake — drop it.

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

## Overloads and Callbacks

- **Prefer union-typed or optional parameters over function overloads.** Overloads hide bugs
  and interact badly with strict null checks; `fn(x: number | string)` and
  `fn(x: string, y?: string)` are clearer than multiple signatures. When overloads are genuinely
  unavoidable, order them specific-to-general — TypeScript resolves to the first matching signature.
- **Type an ignored callback return as `void`**, never `any`; `void` stops callers from
  consuming a value that was never meant to be used.
- **Don't make callback parameters optional.** A callback may legally accept fewer arguments,
  so `(data: Data, count: number) => void` is correct even when some callers ignore `count`.
- **Hand-written `.d.ts` declarations use primitive types** (`string`, `number`, `boolean`,
  `object`), never boxed wrappers (`String`, `Number`, `Boolean`, `Object`).

## Async Patterns

- Always `await` promises; never leave floating promises (use `void` prefix if intentionally fire-and-forget)
- Use `AbortSignal` for cancellation
- Prefer `using` (explicit resource management) for cleanup when targeting environments that support it

## Testing

Test discipline (vitest, behavior through the public interface) lives in `tdd.md`. The gate runs
`vitest` with `--passWithNoTests=false` so a test-less change cannot pass green. Configure
coverage provider, branch thresholds, strict compiler flags, enum/barrel restrictions, and Biome
rules in committed project config (`vitest.config.*`, `tsconfig*.json`, `biome.json`) rather than
only on the gate command line.

## Logging

- Use a structured logger (pino) emitting JSON to stdout; never log to files directly.
- Bind context (request ID, user ID, operation) at entry points and pass child loggers down.

## Documentation

Single-sentence JSDoc explaining WHY the function exists, not WHAT it does. Parameter types and return types are in the signature; do not duplicate them in JSDoc `@param`/`@returns` tags.
