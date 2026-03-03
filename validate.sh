#!/usr/bin/env bash
# validate.sh — Validate all agent-templates artifacts.
# Usage: ./validate.sh [--skills] [--rules] [--hooks] [--smoke] [--settings]
# With no flags, validates everything except smoke tests.
# Bash 3.2 compatible (macOS default).

set -euo pipefail

# --- Color support ---
if [ -t 1 ] && [ "${TERM:-dumb}" != "dumb" ]; then
  GREEN='\033[0;32m'
  RED='\033[0;31m'
  YELLOW='\033[0;33m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN=''
  RED=''
  YELLOW=''
  BOLD=''
  RESET=''
fi

# --- Counters ---
PASS_COUNT=0
FAIL_COUNT=0

pass() {
  PASS_COUNT=$((PASS_COUNT + 1))
  printf "  ${GREEN}PASS${RESET} %s\n" "$1"
}

fail() {
  FAIL_COUNT=$((FAIL_COUNT + 1))
  printf "  ${RED}FAIL${RESET} %s\n" "$1"
}

warn() {
  printf "  ${YELLOW}WARN${RESET} %s\n" "$1"
}

section() {
  printf "\n${BOLD}=== %s ===${RESET}\n" "$1"
}

# --- Frontmatter helpers ---
# Extract YAML frontmatter (lines between first and second ---) from a file.
extract_frontmatter() {
  sed -n '/^---$/,/^---$/p' "$1" | sed '1d;$d'
}

# Check if a frontmatter field exists in a file.
# Usage: has_frontmatter_field <file> <field_name>
has_frontmatter_field() {
  extract_frontmatter "$1" | grep -q "^${2}:"
}

# Get the value of a frontmatter field.
# Usage: get_frontmatter_field <file> <field_name>
get_frontmatter_field() {
  extract_frontmatter "$1" | grep "^${2}:" | sed "s/^${2}:[[:space:]]*//"
}

# --- CLI parsing ---
VALIDATE_SKILLS=false
VALIDATE_RULES=false
VALIDATE_HOOKS=false
VALIDATE_SMOKE=false
VALIDATE_SETTINGS=false

for arg in "$@"; do
  case "$arg" in
    --skills) VALIDATE_SKILLS=true ;;
    --rules) VALIDATE_RULES=true ;;
    --hooks) VALIDATE_HOOKS=true ;;
    --smoke) VALIDATE_SMOKE=true ;;
    --settings) VALIDATE_SETTINGS=true ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

# If no flags provided, validate everything except smoke tests
if [ "$VALIDATE_SKILLS" = false ] && [ "$VALIDATE_RULES" = false ] && \
   [ "$VALIDATE_HOOKS" = false ] && [ "$VALIDATE_SMOKE" = false ] && \
   [ "$VALIDATE_SETTINGS" = false ]; then
  VALIDATE_SKILLS=true
  VALIDATE_RULES=true
  VALIDATE_HOOKS=true
  VALIDATE_SETTINGS=true
fi

# --- Resolve script directory ---
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ===========================================================================
# Skill validation
# ===========================================================================
validate_skills() {
  section "Skills"

  local skill_files
  skill_files=$(find "$SCRIPT_DIR/skills" -path "*/SKILL.md" -type f 2>/dev/null | sort)

  if [ -z "$skill_files" ]; then
    warn "No SKILL.md files found"
    return
  fi

  local old_ifs="$IFS"
  IFS=$'\n'
  for skill_file in $skill_files; do
    IFS="$old_ifs"
    local skill_dir
    skill_dir=$(dirname "$skill_file")
    local skill_name
    skill_name=$(basename "$skill_dir")

    # Check name field exists
    if has_frontmatter_field "$skill_file" "name"; then
      pass "$skill_name: has 'name' field"
    else
      fail "$skill_name: missing 'name' frontmatter field"
    fi

    # Check description field exists
    if has_frontmatter_field "$skill_file" "description"; then
      pass "$skill_name: has 'description' field"

      # Check description starts with "Use when"
      local desc
      desc=$(get_frontmatter_field "$skill_file" "description")
      case "$desc" in
        "Use when"*)
          pass "$skill_name: description starts with 'Use when'"
          ;;
        *)
          fail "$skill_name: description should start with 'Use when', got: $(echo "$desc" | head -c 40)..."
          ;;
      esac
    else
      fail "$skill_name: missing 'description' frontmatter field"
    fi

    # Check for referenced .md files in the skill directory (prompt templates)
    # Look for any .md files other than SKILL.md in the skill directory
    local other_md
    other_md=$(find "$skill_dir" -maxdepth 1 -name "*.md" -not -name "SKILL.md" -type f 2>/dev/null)
    if [ -n "$other_md" ]; then
      local old_ifs2="$IFS"
      IFS=$'\n'
      for md_file in $other_md; do
        IFS="$old_ifs2"
        if [ -f "$md_file" ]; then
          pass "$skill_name: prompt template $(basename "$md_file") exists"
        fi
      done
      IFS="$old_ifs2"
    fi
  done
  IFS="$old_ifs"
}

# ===========================================================================
# Rule validation
# ===========================================================================
validate_rules() {
  section "Rules"

  local rule_files
  rule_files=$(find "$SCRIPT_DIR/rules" -name "*.md" -type f 2>/dev/null | sort)

  if [ -z "$rule_files" ]; then
    warn "No rule .md files found"
    return
  fi

  local old_ifs="$IFS"
  IFS=$'\n'
  for rule_file in $rule_files; do
    IFS="$old_ifs"
    local rule_name
    rule_name=$(basename "$rule_file")

    # Check paths field exists
    if has_frontmatter_field "$rule_file" "paths"; then
      pass "$rule_name: has 'paths' field"

      # Check paths uses comma-separated format (not YAML array)
      local paths_value
      paths_value=$(get_frontmatter_field "$rule_file" "paths")

      # YAML arrays start with [ or have lines starting with -
      case "$paths_value" in
        "["*"]")
          fail "$rule_name: paths uses YAML array format, should use comma-separated quoted strings"
          ;;
        *)
          # Check it looks like comma-separated quoted strings
          if echo "$paths_value" | grep -q '"'; then
            pass "$rule_name: paths uses comma-separated format"
          else
            fail "$rule_name: paths values should be quoted strings"
          fi
          ;;
      esac
    else
      fail "$rule_name: missing 'paths' frontmatter field"
    fi
  done
  IFS="$old_ifs"
}

# ===========================================================================
# Hook validation
# ===========================================================================
validate_hooks() {
  section "Hooks"

  local hook_files
  hook_files=$(find "$SCRIPT_DIR/hooks" -name "*.sh" -type f 2>/dev/null | sort)

  if [ -z "$hook_files" ]; then
    warn "No hook .sh files found"
    return
  fi

  local old_ifs="$IFS"
  IFS=$'\n'
  for hook_file in $hook_files; do
    IFS="$old_ifs"
    local hook_name
    hook_name=$(basename "$hook_file")

    # Check file is executable
    if [ -x "$hook_file" ]; then
      pass "$hook_name: is executable"
    else
      fail "$hook_name: is not executable (run: chmod +x $hook_file)"
    fi

    # Check shebang line
    local first_line
    first_line=$(head -1 "$hook_file")
    if [ "$first_line" = "#!/usr/bin/env bash" ]; then
      pass "$hook_name: has correct shebang"
    else
      fail "$hook_name: shebang should be '#!/usr/bin/env bash', got: $first_line"
    fi

    # Run ShellCheck if available
    if command -v shellcheck >/dev/null 2>&1; then
      if shellcheck --severity=warning --shell=bash "$hook_file" >/dev/null 2>&1; then
        pass "$hook_name: shellcheck passed"
      else
        fail "$hook_name: shellcheck warnings/errors found"
        shellcheck --severity=warning --shell=bash "$hook_file" 2>&1 | head -20 | while IFS= read -r line; do
          printf "         %s\n" "$line"
        done
      fi
    else
      warn "$hook_name: shellcheck not installed, skipping lint"
    fi

    # Hook-specific tests
    case "$hook_name" in
      auto-approve.sh)
        # Test with mock JSON input, validate output is valid JSON
        if command -v jq >/dev/null 2>&1; then
          local mock_input='{"tool_name":"Read","tool_input":{"file_path":"/tmp/test.txt"}}'
          local output
          output=$(echo "$mock_input" | "$hook_file" 2>/dev/null) || true
          if [ -n "$output" ]; then
            if echo "$output" | jq . >/dev/null 2>&1; then
              pass "$hook_name: mock input produces valid JSON output"
            else
              fail "$hook_name: output is not valid JSON: $output"
            fi
          else
            fail "$hook_name: no output for known safe tool 'Read'"
          fi

          # Test with non-safe tool — should produce no output
          local mock_unsafe='{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}'
          local unsafe_output
          unsafe_output=$(echo "$mock_unsafe" | "$hook_file" 2>/dev/null) || true
          if [ -z "$unsafe_output" ]; then
            pass "$hook_name: no output for non-safe tool 'Bash'"
          else
            fail "$hook_name: should not produce output for non-safe tool, got: $unsafe_output"
          fi
        else
          warn "$hook_name: jq not installed, skipping mock test"
        fi
        ;;
      notify-slack.sh)
        # Test with no webhook URL set — should exit silently
        local notify_output
        notify_output=$(CLAUDE_SLACK_WEBHOOK_URL="" "$hook_file" stop 2>&1) || true
        if [ -z "$notify_output" ]; then
          pass "$hook_name: exits silently without webhook URL"
        else
          fail "$hook_name: should be silent without webhook URL, got output: $notify_output"
        fi
        ;;
    esac
  done
  IFS="$old_ifs"
}

# ===========================================================================
# Settings validation
# ===========================================================================
validate_settings() {
  section "Settings"

  local settings_file="$SCRIPT_DIR/templates/settings-hooks.json"

  if [ ! -f "$settings_file" ]; then
    fail "settings-hooks.json: file not found"
    return
  fi

  # Check valid JSON
  if command -v jq >/dev/null 2>&1; then
    if jq . "$settings_file" >/dev/null 2>&1; then
      pass "settings-hooks.json: valid JSON"
    else
      fail "settings-hooks.json: invalid JSON"
      return
    fi

    # Check hook event types are from known list
    local known_events="Notification Stop PreToolUse PostToolUse SessionStart"
    local events
    events=$(jq -r '.hooks | keys[]' "$settings_file" 2>/dev/null) || true

    if [ -z "$events" ]; then
      fail "settings-hooks.json: no hook events found"
    else
      local all_valid=true
      local old_ifs="$IFS"
      IFS=$'\n'
      for event in $events; do
        IFS="$old_ifs"
        local found=false
        for known in $known_events; do
          if [ "$event" = "$known" ]; then
            found=true
            break
          fi
        done
        if [ "$found" = true ]; then
          pass "settings-hooks.json: event '$event' is valid"
        else
          fail "settings-hooks.json: unknown event type '$event'"
          all_valid=false
        fi
      done
      IFS="$old_ifs"
    fi
  else
    warn "settings-hooks.json: jq not installed, skipping validation"
  fi
}

# ===========================================================================
# Smoke test
# ===========================================================================
validate_smoke() {
  section "Smoke Test"

  # Create temp directory with cleanup trap
  local tmpdir
  tmpdir=$(mktemp -d)
  # shellcheck disable=SC2064
  trap "rm -rf '$tmpdir'" EXIT

  # Run install.sh with HOME pointed at tmpdir so hooks/skills/settings
  # all land inside the temp directory instead of the real home.
  printf "  Running installer into temp dir: %s\n" "$tmpdir"
  local install_output
  if install_output=$(HOME="$tmpdir" "$SCRIPT_DIR/install.sh" --target="$tmpdir" --non-interactive --all 2>&1); then
    pass "install.sh exited successfully"
  else
    fail "install.sh exited with non-zero status"
    printf "         %s\n" "$install_output"
    return
  fi

  # --- Check rules ---
  local expected_rules="python.md typescript.md rust.md cpp.md"
  for rule in $expected_rules; do
    if [ -f "$tmpdir/.claude/rules/$rule" ]; then
      pass "rule installed: $rule"
    else
      fail "rule missing: $tmpdir/.claude/rules/$rule"
    fi
  done

  # --- Check skills ---
  # All skill directories with content should have SKILL.md installed
  local expected_skills="clean-code-planner python-coding-rules implement-orchestrator plan-codebase plan-tests implement-parallel review-parallel"
  for skill in $expected_skills; do
    if [ -f "$tmpdir/.claude/skills/$skill/SKILL.md" ]; then
      pass "skill installed: $skill/SKILL.md"
    else
      fail "skill missing: $tmpdir/.claude/skills/$skill/SKILL.md"
    fi
  done

  # --- Check hooks ---
  local expected_hooks="auto-approve.sh notify-slack.sh"
  for hook in $expected_hooks; do
    if [ -f "$tmpdir/.claude/hooks/$hook" ]; then
      pass "hook installed: $hook"
      # Verify hooks are executable
      if [ -x "$tmpdir/.claude/hooks/$hook" ]; then
        pass "hook executable: $hook"
      else
        fail "hook not executable: $hook"
      fi
    else
      fail "hook missing: $tmpdir/.claude/hooks/$hook"
    fi
  done

  # --- Check settings.json ---
  if [ -f "$tmpdir/.claude/settings.json" ]; then
    pass "settings.json installed"

    # Validate JSON if jq is available
    if command -v jq >/dev/null 2>&1; then
      if jq . "$tmpdir/.claude/settings.json" >/dev/null 2>&1; then
        pass "settings.json is valid JSON"
      else
        fail "settings.json is not valid JSON"
      fi
    else
      warn "jq not installed, skipping JSON validation of settings.json"
    fi
  else
    fail "settings.json missing: $tmpdir/.claude/settings.json"
  fi

  # --- Check CLAUDE.md template ---
  if [ -f "$tmpdir/CLAUDE.md" ]; then
    pass "CLAUDE.md installed"
  else
    fail "CLAUDE.md missing: $tmpdir/CLAUDE.md"
  fi

  # Clean up (trap handles this, but be explicit)
  rm -rf "$tmpdir"
  trap - EXIT
}

# ===========================================================================
# Main
# ===========================================================================

printf "${BOLD}agent-templates validation${RESET}\n"

if [ "$VALIDATE_SKILLS" = true ]; then
  validate_skills
fi

if [ "$VALIDATE_RULES" = true ]; then
  validate_rules
fi

if [ "$VALIDATE_HOOKS" = true ]; then
  validate_hooks
fi

if [ "$VALIDATE_SETTINGS" = true ]; then
  validate_settings
fi

if [ "$VALIDATE_SMOKE" = true ]; then
  validate_smoke
fi

# --- Summary ---
printf "\n${BOLD}--- Summary ---${RESET}\n"
printf "  ${GREEN}%d passed${RESET}, ${RED}%d failed${RESET}\n" "$PASS_COUNT" "$FAIL_COUNT"

if [ "$FAIL_COUNT" -gt 0 ]; then
  exit 1
fi

exit 0
