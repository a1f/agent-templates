# Research: Validation & Smoke Testing Patterns

## YAML Frontmatter Validation

### Primary: Pure bash (zero deps)
```bash
extract_frontmatter() {
  sed -n '/^---$/,/^---$/p' "$1" | sed '1d;$d'
}
validate_frontmatter_field() {
  extract_frontmatter "$1" | grep -q "^${2}:"
}
```

### Enhanced: yq (if available)
```bash
yq --front-matter=extract '.name // ""' "$file"
```

## JSON Validation

Use `jq` for structural validation:
```bash
# Syntax check
jq . "$file" >/dev/null 2>&1

# Schema check (expected keys)
jq 'has("hooks")' "$file"

# Validate event types
jq -r '.hooks | keys[]' "$file" | while read event; do
  # check against known events
done
```

No need for external schema tools (ajv, jsonschema). jq is sufficient.

## Smoke Testing

Install to temp dir and verify:
```bash
smoke_test() {
  local tmpdir=$(mktemp -d)
  trap "rm -rf '$tmpdir'" EXIT

  ./install.sh --target="$tmpdir" --non-interactive --all

  # Verify files exist
  [[ -f "$tmpdir/.claude/rules/python.md" ]] || fail "Missing python.md"
  # Verify hooks executable
  [[ -x "$tmpdir/.claude/hooks/notify-slack.sh" ]] || fail "Hook not executable"
  # Verify JSON valid
  jq . "$tmpdir/.claude/settings.json" >/dev/null 2>&1 || fail "Invalid JSON"
}
```

## Shell Script Quality

### ShellCheck (mandatory)
Run on all `.sh` files. Catches: unquoted variables, useless cat, missing shebangs, word splitting.
```bash
shellcheck --severity=warning --shell=bash hooks/*.sh install.sh validate.sh
```

### bats-core (integration tests)
```bash
@test "notify-slack exits silently without webhook URL" {
  unset CLAUDE_SLACK_WEBHOOK_URL
  run ./hooks/notify-slack.sh stop
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
```

## Validation Script Structure

```bash
./validate.sh              # All checks
./validate.sh --skills     # SKILL.md frontmatter + structure
./validate.sh --rules      # Rules frontmatter + glob patterns
./validate.sh --hooks      # Executable, shebang, output format
./validate.sh --smoke      # Full install to temp dir
```

## Sources

- [yq front matter support](https://mikefarah.gitbook.io/yq/usage/front-matter)
- [ShellCheck](https://www.shellcheck.net/)
- [bats-core](https://github.com/bats-core/bats-core)
