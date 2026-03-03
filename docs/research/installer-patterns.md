# Research: Bash Installer Patterns

## Menu: Simple `read` (bash 3.2 compatible)

Use `read -rp` for interactive menu. Zero dependencies, works on macOS bash 3.2.

Add `--non-interactive` flag accepting component numbers as arguments for CI/automation.

## JSON Config Merging

### Deep merge with jq
```bash
jq -s '.[0] * .[1]' existing.json new.json
```

The `*` operator recursively merges nested objects. Preserves existing hooks while adding new ones.

**Fallback:** If jq not installed, print manual merge instructions.

## Backup/Rollback

Timestamped backups with manifest:
```bash
backup_file() {
  local file="$1"
  [[ -f "$file" ]] || return 0
  local backup="${file}.bak.$(date +%s)"
  cp "$file" "$backup"
  echo "$backup:$file" >> "$BACKUP_MANIFEST"
}
```

Rollback via `trap rollback ERR` reads manifest and restores originals.

## Dry-Run

Wrapper function pattern:
```bash
install_file() {
  local src="$1" dst="$2"
  if [[ "$DRY_RUN" == "true" ]]; then
    echo "[DRY RUN] Would create: $dst"
    [[ -f "$dst" ]] && diff --color "$dst" "$src" 2>/dev/null || true
  else
    backup_file "$dst"
    cp "$src" "$dst"
  fi
}
```

## Cross-Platform (macOS + Linux)

Target **bash 3.2** (macOS default since 2007, GPLv2).

**Avoid:** associative arrays (`declare -A`), `${var,,}`, `readarray`/`mapfile`, `|&`

**Safe alternatives:**
- `while IFS= read -r line; do arr+=("$line"); done < file` instead of `readarray`
- `$(echo "$val" | tr '[:upper:]' '[:lower:]')` instead of `${var,,}`

**Other gotchas:** `date -d` (Linux only), `sed -i ''` vs `sed -i` (use `sed -i.bak`), `realpath` not on older macOS.

## Patterns Borrowed from Dotfile Managers

From **chezmoi**: copy-not-symlink, dry-run, diff-before-overwrite, timestamped backups.
From **Stow**: package-based organization (each component installed independently).

## Sources

- [Shell Script Best Practices](https://sharats.me/posts/shell-script-best-practices/)
- [chezmoi](https://www.chezmoi.io/why-use-chezmoi/)
- [Merge JSON with jq](https://richrose.dev/posts/linux/jq/jq-jsonmerge/)
