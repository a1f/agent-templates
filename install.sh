#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# Claude Code Agent Templates Installer
# =============================================================================
# Interactive installer for rules, skills, and hooks.
# Works on macOS (bash 3.2) and Linux.
#
# Usage:
#   ./install.sh                                    # Interactive mode
#   ./install.sh --non-interactive --all            # Install everything
#   ./install.sh --dry-run --all                    # Preview changes
#   ./install.sh --uninstall                        # Restore backups
#   ./install.sh --target=/path/to/project          # Specify target project
# =============================================================================

# --- Bash version check ------------------------------------------------------
if [[ "${BASH_VERSINFO[0]}" -lt 3 ]]; then
  echo "Error: bash 3.2+ required (found ${BASH_VERSION})"
  exit 1
fi

# --- Resolve script directory -------------------------------------------------
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# --- Defaults -----------------------------------------------------------------
DRY_RUN="false"
UNINSTALL="false"
TARGET_DIR=""
NON_INTERACTIVE="false"
INSTALL_ALL="false"
BACKUP_MANIFEST=""

# --- Color helpers (degrade gracefully) ---------------------------------------
if [ -t 1 ]; then
  BOLD="\033[1m"
  GREEN="\033[32m"
  YELLOW="\033[33m"
  RED="\033[31m"
  CYAN="\033[36m"
  RESET="\033[0m"
else
  BOLD=""
  GREEN=""
  YELLOW=""
  RED=""
  CYAN=""
  RESET=""
fi

# --- Logging helpers ----------------------------------------------------------
info()  { printf "${GREEN}[INFO]${RESET}  %s\n" "$*"; }
warn()  { printf "${YELLOW}[WARN]${RESET}  %s\n" "$*"; }
error() { printf "${RED}[ERROR]${RESET} %s\n" "$*" >&2; }
dry()   { printf "${CYAN}[DRY RUN]${RESET} %s\n" "$*"; }

# --- Parse CLI flags ----------------------------------------------------------
for arg in "$@"; do
  case "$arg" in
    --dry-run)
      DRY_RUN="true"
      ;;
    --uninstall)
      UNINSTALL="true"
      ;;
    --target=*)
      TARGET_DIR="${arg#--target=}"
      ;;
    --non-interactive)
      NON_INTERACTIVE="true"
      ;;
    --all)
      INSTALL_ALL="true"
      ;;
    --help|-h)
      echo "Usage: $0 [OPTIONS]"
      echo ""
      echo "Options:"
      echo "  --dry-run            Show what would be done without making changes"
      echo "  --uninstall          Restore files from backup manifest"
      echo "  --target=<path>      Target project directory (default: current directory)"
      echo "  --non-interactive    Do not prompt for input"
      echo "  --all                Install all components"
      echo "  -h, --help           Show this help message"
      exit 0
      ;;
    *)
      error "Unknown option: $arg"
      echo "Run '$0 --help' for usage."
      exit 1
      ;;
  esac
done

# --- Resolve target directory -------------------------------------------------
if [ -z "$TARGET_DIR" ]; then
  TARGET_DIR="$(pwd)"
fi

# Ensure target directory exists
if [ ! -d "$TARGET_DIR" ]; then
  error "Target directory does not exist: $TARGET_DIR"
  exit 1
fi

# Resolve to absolute path (bash 3.2 compatible - no realpath)
TARGET_DIR="$( cd "$TARGET_DIR" && pwd )"

# --- Set backup manifest path -------------------------------------------------
BACKUP_MANIFEST="${TARGET_DIR}/.claude/.install-backup-manifest"

# =============================================================================
# Helper Functions
# =============================================================================

# backup_file() — create timestamped backup and record in manifest
backup_file() {
  local file="$1"
  [ -f "$file" ] || return 0

  local backup="${file}.bak.$(date +%s)"
  cp "$file" "$backup"

  # Ensure manifest directory exists
  local manifest_dir
  manifest_dir="$(dirname "$BACKUP_MANIFEST")"
  if [ ! -d "$manifest_dir" ]; then
    mkdir -p "$manifest_dir"
  fi

  echo "${backup}:${file}" >> "$BACKUP_MANIFEST"
  info "Backed up: $file -> $backup"
}

# install_file() — dry-run aware copy with backup
install_file() {
  local src="$1"
  local dst="$2"

  if [ "$DRY_RUN" = "true" ]; then
    dry "Would copy: $src -> $dst"
    if [ -f "$dst" ]; then
      dry "File exists, showing diff:"
      diff "$dst" "$src" 2>/dev/null || true
    fi
    return 0
  fi

  # Ensure destination directory exists
  local dst_dir
  dst_dir="$(dirname "$dst")"
  if [ ! -d "$dst_dir" ]; then
    mkdir -p "$dst_dir"
    info "Created directory: $dst_dir"
  fi

  backup_file "$dst"
  cp "$src" "$dst"
  info "Installed: $dst"
}

# install_file_executable() — install_file + chmod +x
install_file_executable() {
  local src="$1"
  local dst="$2"

  install_file "$src" "$dst"

  if [ "$DRY_RUN" = "true" ]; then
    dry "Would make executable: $dst"
    return 0
  fi

  chmod +x "$dst"
}

# show_diff() — show diff if target exists
show_diff() {
  local src="$1"
  local dst="$2"

  if [ -f "$dst" ]; then
    echo ""
    echo "--- Diff: $dst (existing) vs $src (new) ---"
    diff "$dst" "$src" 2>/dev/null || true
    echo "--- End diff ---"
    echo ""
  fi
}

# rollback() — read manifest and restore originals
rollback() {
  if [ ! -f "$BACKUP_MANIFEST" ]; then
    warn "No backup manifest found at: $BACKUP_MANIFEST"
    return 1
  fi

  info "Reading backup manifest: $BACKUP_MANIFEST"

  local count=0
  while IFS=: read -r backup_path original_path; do
    # Skip empty lines
    [ -z "$backup_path" ] && continue

    if [ "$DRY_RUN" = "true" ]; then
      dry "Would restore: $backup_path -> $original_path"
      count=$((count + 1))
      continue
    fi

    if [ -f "$backup_path" ]; then
      cp "$backup_path" "$original_path"
      rm "$backup_path"
      info "Restored: $original_path (from $backup_path)"
      count=$((count + 1))
    else
      warn "Backup file missing, skipping: $backup_path"
    fi
  done < "$BACKUP_MANIFEST"

  if [ "$DRY_RUN" != "true" ]; then
    rm "$BACKUP_MANIFEST"
    info "Removed backup manifest"
  fi

  info "Rollback complete: $count file(s) restored"
}

# =============================================================================
# Component Installers
# =============================================================================

# install_rules() — copies rules/*.md -> <target>/.claude/rules/
install_rules() {
  local rules_src="${SCRIPT_DIR}/rules"
  local rules_dst="${TARGET_DIR}/.claude/rules"

  echo ""
  printf "${BOLD}Installing Language Rules${RESET}\n"
  echo "  Source: $rules_src"
  echo "  Target: $rules_dst"
  echo ""

  if [ ! -d "$rules_src" ]; then
    warn "Rules source directory not found: $rules_src"
    return 0
  fi

  local found_rules="false"
  for rule_file in "$rules_src"/*.md; do
    # Guard against empty glob
    [ -f "$rule_file" ] || continue
    found_rules="true"

    local filename
    filename="$(basename "$rule_file")"
    local dst="${rules_dst}/${filename}"

    if [ -f "$dst" ] && [ "$NON_INTERACTIVE" != "true" ] && [ "$DRY_RUN" != "true" ]; then
      show_diff "$rule_file" "$dst"
      printf "  File exists: %s. Overwrite? [y/N] " "$filename"
      read -r answer
      case "$answer" in
        [yY]|[yY][eE][sS])
          install_file "$rule_file" "$dst"
          ;;
        *)
          info "Skipped: $filename"
          ;;
      esac
    else
      install_file "$rule_file" "$dst"
    fi
  done

  if [ "$found_rules" = "false" ]; then
    warn "No rule files found in $rules_src"
  fi
}

# install_skills() — copies skills/*/ -> ~/.claude/skills/
install_skills() {
  local skills_src="${SCRIPT_DIR}/skills"
  local skills_dst="${HOME}/.claude/skills"

  echo ""
  printf "${BOLD}Installing Skills${RESET}\n"
  echo "  Source: $skills_src"
  echo "  Target: $skills_dst"
  echo ""

  if [ ! -d "$skills_src" ]; then
    warn "Skills source directory not found: $skills_src"
    return 0
  fi

  local found_skills="false"
  for skill_dir in "$skills_src"/*/; do
    # Guard against empty glob
    [ -d "$skill_dir" ] || continue

    local skill_name
    skill_name="$(basename "$skill_dir")"

    # Skip if skill directory only has .gitkeep
    local has_content="false"
    for item in "$skill_dir"*; do
      local item_name
      item_name="$(basename "$item")"
      if [ "$item_name" != ".gitkeep" ]; then
        has_content="true"
        break
      fi
    done

    if [ "$has_content" = "false" ]; then
      info "Skipping empty skill: $skill_name"
      continue
    fi

    found_skills="true"
    local dst_skill_dir="${skills_dst}/${skill_name}"

    if [ "$DRY_RUN" = "true" ]; then
      dry "Would create directory: $dst_skill_dir"
    else
      if [ ! -d "$dst_skill_dir" ]; then
        mkdir -p "$dst_skill_dir"
        info "Created directory: $dst_skill_dir"
      fi
    fi

    # Copy all files in skill directory (excluding .gitkeep)
    for skill_file in "$skill_dir"*; do
      [ -f "$skill_file" ] || continue
      local fname
      fname="$(basename "$skill_file")"
      [ "$fname" = ".gitkeep" ] && continue

      install_file "$skill_file" "${dst_skill_dir}/${fname}"
    done
  done

  if [ "$found_skills" = "false" ]; then
    warn "No skills with content found in $skills_src"
  fi
}

# install_hooks() — copies hooks/*.sh -> ~/.claude/hooks/, merges settings
install_hooks() {
  local hooks_src="${SCRIPT_DIR}/hooks"
  local hooks_dst="${HOME}/.claude/hooks"
  local settings_src="${SCRIPT_DIR}/templates/settings-hooks.json"
  local settings_dst="${HOME}/.claude/settings.json"

  echo ""
  printf "${BOLD}Installing Hooks${RESET}\n"
  echo "  Hook source: $hooks_src"
  echo "  Hook target: $hooks_dst"
  echo "  Settings:    $settings_dst"
  echo ""

  if [ ! -d "$hooks_src" ]; then
    warn "Hooks source directory not found: $hooks_src"
    return 0
  fi

  # Install hook scripts
  for hook_file in "$hooks_src"/*.sh; do
    [ -f "$hook_file" ] || continue
    local filename
    filename="$(basename "$hook_file")"
    install_file_executable "$hook_file" "${hooks_dst}/${filename}"
  done

  # Merge hook settings into settings.json
  if [ -f "$settings_src" ]; then
    echo ""
    info "Merging hook configuration into settings.json..."

    if [ "$DRY_RUN" = "true" ]; then
      dry "Would merge $settings_src into $settings_dst"
      if [ -f "$settings_dst" ]; then
        dry "Existing settings.json found, would deep-merge"
      else
        dry "No existing settings.json, would create new"
      fi
      return 0
    fi

    if command -v jq >/dev/null 2>&1; then
      if [ -f "$settings_dst" ]; then
        backup_file "$settings_dst"
        local merged
        merged="$(jq -s '.[0] * .[1]' "$settings_dst" "$settings_src")"
        echo "$merged" > "$settings_dst"
        info "Deep-merged hook config into existing settings.json"
      else
        # Ensure directory exists
        local settings_dir
        settings_dir="$(dirname "$settings_dst")"
        if [ ! -d "$settings_dir" ]; then
          mkdir -p "$settings_dir"
        fi
        cp "$settings_src" "$settings_dst"
        info "Created settings.json with hook configuration"
      fi
    else
      warn "jq not found — cannot auto-merge settings.json"
      echo ""
      echo "  Please manually merge the following into $settings_dst:"
      echo ""
      echo "  --- settings-hooks.json contents ---"
      cat "$settings_src"
      echo ""
      echo "  --- end ---"
      echo ""
      echo "  Install jq for automatic merging: brew install jq (macOS) or apt install jq (Linux)"
    fi
  fi
}

# =============================================================================
# Main
# =============================================================================

# --- Uninstall mode ---
if [ "$UNINSTALL" = "true" ]; then
  echo ""
  printf "${BOLD}Claude Code Agent Templates — Uninstall${RESET}\n"
  echo "========================================"
  echo ""
  echo "  Target: $TARGET_DIR"
  echo "  Manifest: $BACKUP_MANIFEST"
  echo ""

  if [ "$DRY_RUN" = "true" ]; then
    dry "Preview of rollback:"
    echo ""
  fi

  rollback
  exit 0
fi

# --- Install mode ---
echo ""
printf "${BOLD}Claude Code Agent Templates Installer${RESET}\n"
echo "======================================"
echo ""
echo "  Target: $TARGET_DIR"
if [ "$DRY_RUN" = "true" ]; then
  echo "  Mode:   DRY RUN (no changes will be made)"
fi
echo ""

if [ "$INSTALL_ALL" = "true" ]; then
  # Install everything
  install_rules
  install_skills
  install_hooks

  echo ""
  echo "======================================"
  if [ "$DRY_RUN" = "true" ]; then
    dry "Dry run complete — no files were changed"
  else
    info "Installation complete!"
    echo ""
    echo "  Next steps:"
    echo "    1. Set CLAUDE_SLACK_WEBHOOK_URL for Slack notifications"
    echo "    2. Review .claude/rules/ for language-specific conventions"
  fi
  echo ""
  exit 0
fi

if [ "$NON_INTERACTIVE" = "true" ]; then
  error "Non-interactive mode requires --all or specific component flags"
  echo "  Usage: $0 --non-interactive --all"
  exit 1
fi

# --- Interactive menu ---
while true; do
  echo ""
  echo "  What would you like to install?"
  echo ""
  echo "    [1] Language Rules (python, typescript, rust, cpp)"
  echo "    [2] Skills (agentic workflow pipeline)"
  echo "    [3] Hooks (Slack notifications, auto-approve)"
  echo "    [4] Everything"
  echo "    [0] Exit"
  echo ""
  printf "  Select options (comma-separated): "
  read -r choices

  # Normalize: remove spaces
  choices="$(echo "$choices" | tr -d ' ')"

  if [ -z "$choices" ]; then
    continue
  fi

  # Parse comma-separated choices
  # Save and restore IFS (bash 3.2 compatible)
  OLD_IFS="$IFS"
  IFS=","
  set -- $choices
  IFS="$OLD_IFS"

  local_exit="false"
  for choice in "$@"; do
    case "$choice" in
      0)
        local_exit="true"
        ;;
      1)
        install_rules
        ;;
      2)
        install_skills
        ;;
      3)
        install_hooks
        ;;
      4)
        install_rules
        install_skills
        install_hooks
        ;;
      *)
        warn "Unknown option: $choice"
        ;;
    esac
  done

  if [ "$local_exit" = "true" ]; then
    break
  fi

  echo ""
  echo "======================================"
  if [ "$DRY_RUN" = "true" ]; then
    dry "Dry run — no files were changed"
  else
    info "Done! Select more options or [0] to exit."
  fi
done

echo ""
info "Goodbye!"
