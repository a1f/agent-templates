# Research: TypeScript Best Practices (2025-2026)

## Target: TypeScript 5.8+

TS 7.0 (mid-2026) will be rewritten in Go with 10x faster builds and strict-by-default. Prepare by using `module: "nodenext"` now.

## Tooling Decisions

| Tool | Choice | Rationale |
|------|--------|-----------|
| Linter/Formatter | **Biome** (preferred) or ESLint+Prettier | Biome v2 stable, 10-25x faster, 1 config file vs 3-4. ~75% type-aware coverage. |
| Package manager | **pnpm** | Strictest deps (no phantom), best disk efficiency, most mature monorepo support. |
| Test framework | **vitest** | Clear winner. 10x faster than Jest in watch mode. Native TS/ESM support. |
| Validation | **Zod** (or Valibot for bundle-sensitive) | Largest ecosystem (78+ integrations). Standard Schema v1 compliant. |
| Result types | **neverthrow** or custom discriminated union | Pattern matters more than library. Custom is ~20 lines, zero deps. |
| Monorepo | **Turborepo** | Simpler than Nx, purpose-built for JS/TS. |

## Rules: Key Changes from Original Design

### CHANGED:
- ~~prettier + eslint~~ → **Biome** (preferred) or ESLint + Prettier
- ~~strict mode (no any)~~ → strict mode **+ 3 extra flags** (see below)
- ~~zod for validation~~ → Zod (or Valibot); prefer Standard Schema compliance
- ~~Result types for errors~~ → Result types via neverthrow or custom discriminated union

### ADDED:
1. **No enums** — prefer `as const` objects with derived union types:
   ```typescript
   const Status = { Active: "active", Inactive: "inactive" } as const;
   type Status = (typeof Status)[keyof typeof Status];
   ```
2. **No barrel exports** — use direct file imports. Barrels only at package public API boundaries. (Atlassian: 75% faster builds after removing barrel files)
3. **Module system** — `"module": "nodenext"`, never CommonJS for new code
4. **Extra strict flags**:
   ```json
   {
     "strict": true,
     "noUncheckedIndexedAccess": true,
     "exactOptionalPropertyTypes": true,
     "noPropertyAccessFromIndexSignature": true
   }
   ```
5. **`unknown` over `any`** — use `unknown` with type narrowing when dynamic type needed

## Key Research Findings

### Biome vs ESLint+Prettier
- Biome v2: stable, Rust-based, 1 binary, type-aware linting without tsc
- ~75-85% of typescript-eslint rule coverage (gap closing)
- Plugin system via GritQL for custom rules
- ESLint still has larger plugin ecosystem (1000+ vs new)

### No Enums Rationale
- Enums generate runtime IIFE code (increases bundle)
- Conflicts with "erasable types" direction (Node's native TS support)
- `as const` objects produce natural union types, better tree-shaking

### No Barrel Exports Rationale
- Atlassian/Jira: 75% build time reduction after removing barrels
- Next.js project: 68% module count reduction
- Primary source of circular import issues

## Sources

- [Biome v2](https://biomejs.dev/blog/biome-v2/) | [Biome Roadmap 2026](https://biomejs.dev/blog/roadmap-2026/)
- [TypeScript 5.8](https://devblogs.microsoft.com/typescript/announcing-typescript-5-8/) | [TS 7.0 Progress](https://devblogs.microsoft.com/typescript/progress-on-typescript-7-december-2025/)
- [Standard Schema](https://github.com/standard-schema/standard-schema)
- [Atlassian: Faster Builds Without Barrel Files](https://www.atlassian.com/blog/atlassian-engineering/faster-builds-when-removing-barrel-files)
- [Please Stop Using Barrel Files (TkDodo)](https://tkdodo.eu/blog/please-stop-using-barrel-files)
