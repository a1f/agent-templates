# Research: Claude Code Conditional Rules Format

## Current State of the Art

Claude Code conditional rules are markdown files stored in `.claude/rules/` that load automatically when Claude works with matching file types. They use YAML frontmatter with glob patterns to specify which files trigger the rule.

## Format Specification

### File Location

| Scope | Path | Behavior |
|-------|------|----------|
| Project | `<project>/.claude/rules/*.md` | Applies to this project only |
| User | `~/.claude/rules/*.md` | Applies to all projects |

### YAML Frontmatter

```yaml
---
paths: src/**/*.ts, tests/**/*.test.ts
---
```

**Supported fields:**
- `paths:` — comma-separated glob patterns (recommended)
- `globs:` — alternative to paths (same behavior, also works)
- `name:` — optional identifier
- `description:` — optional metadata

### Critical Format Quirk

**DO NOT use YAML array syntax for paths** — it fails silently:

```yaml
# BAD — fails silently, rule never loads
---
paths:
  - "**/*.py"
  - "**/pyproject.toml"
---

# GOOD — comma-separated, works reliably
---
paths: "**/*.py", "**/pyproject.toml"
---

# ALSO GOOD — globs field
---
globs: "**/*.py", "**/pyproject.toml"
---
```

This is a known bug: [GitHub Issue #13905](https://github.com/anthropics/claude-code/issues/13905), [Issue #17204](https://github.com/anthropics/claude-code/issues/17204).

### Glob Pattern Examples

| Pattern | Matches |
|---------|---------|
| `**/*.ts` | All TypeScript files anywhere |
| `src/api/**/*.ts` | TS files in src/api and subdirs |
| `**/*.{ts,tsx}` | Both .ts and .tsx files |
| `{src,lib}/**/*.ts` | TS files in either src/ or lib/ |
| `*.md` | Markdown files in root only |

### Markdown Body

Standard markdown after frontmatter. No specific structure required — content is injected into Claude's context when matching files are active.

## Loading Behavior

1. **Unconditional rules** — no `paths:` field → always loaded
2. **Conditional rules** — `paths:` field → loaded only when Claude works with matching files
3. **Priority** — file-specific rules get higher context priority
4. **Scope** — project rules in `.claude/rules/`, user rules in `~/.claude/rules/`

## Alternatives Evaluated

- **CLAUDE.md only**: No conditional loading, all rules always in context (wastes tokens)
- **Skills for rules**: Overkill — skills are for workflows, rules are for conventions
- **Per-file comments**: Not reusable across projects

**Recommendation:** Conditional rules with `paths:` frontmatter are the right choice. Use comma-separated format (not YAML arrays) to avoid the known parsing bug.

## Key Findings for Implementation

1. Use `paths: "**/*.py", "**/pyproject.toml"` format (comma-separated, quoted)
2. NEVER use YAML array syntax for paths — it silently fails
3. Rules are pure markdown after frontmatter — keep them concise
4. Project-level rules go in `.claude/rules/`, not user-level
5. Name files descriptively: `python.md`, `typescript.md`, etc.
6. Consider `globs:` as alternative field name (works the same)

## Sources

- [Claude Code Docs: Manage Claude's memory](https://code.claude.com/docs/en/memory)
- [GitHub Issue #13905: Invalid YAML syntax in rules frontmatter](https://github.com/anthropics/claude-code/issues/13905)
- [GitHub Issue #17204: Documentation frontmatter format incorrect](https://github.com/anthropics/claude-code/issues/17204)
- [GitHub Issue #23569: Path-conditional rules ignored in worktree](https://github.com/anthropics/claude-code/issues/23569)
