---
name: issue-make
description: Use when the user wants to create or update a GitHub issue with project linking and planning artifact attachment, or invokes /issue-make. Also called by /make-pr for issue lifecycle.
---

# Issue Make

Create or update a GitHub issue, link it to a GitHub Project, and attach repo-root planning `.md` files as a gist. Idempotent — re-running updates the existing issue rather than creating a duplicate.

```
/issue-make [--title="..."] [--issue=N] [--labels=bug,enhancement] [--assignee=@me] [--project="..."] [--attach-md]

  1. Gather repo info
  2. Find or create issue (idempotent)
  3. Attach planning .md files as a gist
  4. Link to a GitHub Project
  5. Print summary
```

## Prerequisites

The `gh` CLI must be authenticated with:
- `repo` — read/write access to repository
- `read:project` + `project` — for project linking

If project scopes are missing, run:
```bash
gh auth refresh -s read:project,project
```

The skill will still create the issue without project scopes — it just skips project linking and warns.

## Arguments

Parse arguments from the user's message or from the calling skill. All are optional:

| Arg | Default | Example |
|-----|---------|---------|
| `--issue=N` | Auto-detect or create | `--issue=42` |
| `--title="..."` | From conversation context | `--title="Fix auth timeout"` |
| `--labels=l1,l2` | None | `--labels=bug,P1` |
| `--assignee=user` | `@me` | `--assignee=alice` |
| `--project="..."` | Auto-detect | `--project="Backend"` |
| `--milestone="..."` | None | `--milestone="v2.1"` |
| `--attach-md` | `true` | `--attach-md=false` to skip |

## Phase 1: Gather Info

Run in parallel:

```bash
OWNER=$(gh repo view --json owner -q '.owner.login')
REPO=$(gh repo view --json name -q '.name')
CURRENT_USER=$(gh api user -q '.login')
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
```

## Phase 2: Find or Create Issue (Idempotent)

### 2a. Detect Existing Issue

Priority order:
1. `--issue=N` argument → use that
2. Branch name contains issue number (e.g., `feat/42-add-auth`, `fix-42`) → use that
3. Commit messages contain `#N` references → use that
4. Search open issues by title match (if `--title` provided):
   ```bash
   gh issue list --state open --search "$ISSUE_TITLE" --json number,title --jq '.[0]'
   ```
5. No issue found → create one in 2b

If an existing issue is found, verify it's still open. If closed, create a new one.

### 2b. Create Issue (if none found)

**Title:** Use `--title` if provided. Otherwise derive from conversation context:
- If the user described a bug or feature, summarize in under 70 characters
- If `plan.md` exists and was referenced, use its first heading

**Body:** Build from the user's description:

```markdown
## Description

<User's description or conversation context summarized clearly>

## Acceptance Criteria

- [ ] <derived from the user's request>
```

Do not invent requirements the user didn't mention.

```bash
gh issue create \
  --title "$ISSUE_TITLE" \
  --body "$ISSUE_BODY" \
  --assignee "${ARG_ASSIGNEE:-@me}" \
  ${LABELS:+--label "$LABELS"} \
  ${MILESTONE:+--milestone "$MILESTONE"}
```

### 2c. Update Existing Issue (if found)

If an existing issue was found, update it if new information is available:
- Add labels if `--labels` provided and not already present
- Update assignee if `--assignee` provided and different
- Do NOT overwrite the title or body — the existing content is authoritative

This makes the skill idempotent: running it twice with the same inputs produces the same result.

## Phase 3: Attach Planning .md Files

Skip if `--attach-md=false`.

### 3a. Find Planning Artifacts

Glob for `*.md` files at the repository root:
```bash
REPO_ROOT=$(git rev-parse --show-toplevel)
ls "$REPO_ROOT"/*.md 2>/dev/null
```

**Exclude** standard repo docs (not planning artifacts):
- `README.md`
- `CHANGELOG.md`
- `LICENSE.md`
- `CONTRIBUTING.md`
- `CODE_OF_CONDUCT.md`
- `CLAUDE.md`

**Include** everything else — these are planning artifacts:
- `plan.md`, `issues.md`, `improvements.md`, `spec.md`, `design.md`, etc.

If no planning `.md` files found, skip this phase.

### 3b. Check for Existing Gist Comment

Before creating a new gist, check if a planning gist is already attached:
```bash
gh api "repos/$OWNER/$REPO/issues/$ISSUE_NUMBER/comments" \
  --paginate \
  -q '.[] | select(.body | contains("## Planning Artifacts")) | .id' \
  | head -1
```

If a comment with "## Planning Artifacts" exists, update it (delete old comment, post new one). This keeps the skill idempotent.

### 3c. Create Gist with .md Contents

Create a single gist containing all planning `.md` files with their **full contents**:

```bash
# Build gist command with each .md file
gh gist create \
  --desc "Planning artifacts for #${ISSUE_NUMBER}" \
  file1.md file2.md file3.md ...
```

**Important:** The gist must contain the actual file contents, not file paths. This ensures the planning context is accessible from any machine via the issue.

### 3d. Post Comment on Issue

```bash
gh issue comment "$ISSUE_NUMBER" --body "## Planning Artifacts

Planning documents attached as a gist: ${GIST_URL}

Files included:
$(for f in $MD_FILES; do echo "- \`$(basename $f)\`"; done)

_Updated by \`/issue-make\` — re-run to refresh._"
```

## Phase 4: Link to Project

### 4a. Pre-check

Skip if `--project=none` is explicitly passed.

Check if the issue is already in a project:
```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!, $number: Int!) {
    repository(owner: $owner, name: $repo) {
      issue(number: $number) {
        projectItems(first: 1) {
          totalCount
        }
      }
    }
  }' -f owner="$OWNER" -f repo="$REPO" -F number="$ISSUE_NUMBER" \
  -q '.data.repository.issue.projectItems.totalCount'
```
If totalCount > 0, skip — already linked.

### 4b. Find Project

If `--project="Name"` is provided, find the matching project:
```bash
gh api graphql -f query='
  query($owner: String!, $repo: String!) {
    repository(owner: $owner, name: $repo) {
      projectsV2(first: 10) {
        nodes { id title }
      }
    }
  }' -f owner="$OWNER" -f repo="$REPO" \
  -q '.data.repository.projectsV2.nodes'
```
Match by title (case-insensitive). If no match, warn and skip.

If no `--project` argument, auto-detect:
1. **If exactly 1 project** → use it
2. **If multiple projects** → pick the one most recently used by closed issues:
   ```bash
   gh api graphql -f query='
     query($owner: String!, $repo: String!) {
       repository(owner: $owner, name: $repo) {
         issues(states: CLOSED, last: 10) {
           nodes {
             projectItems(first: 1) {
               nodes {
                 project { id title }
               }
             }
           }
         }
       }
     }' -f owner="$OWNER" -f repo="$REPO"
   ```
   Count which project appears most frequently and use that one.
3. **If no projects** → skip, no warning needed
4. **If token lacks `read:project` scope** → skip, warn user to run `gh auth refresh -s read:project,project`

### 4c. Add Issue to Project

```bash
ISSUE_NODE_ID=$(gh api "repos/$OWNER/$REPO/issues/$ISSUE_NUMBER" -q '.node_id')

gh api graphql -f query='
  mutation($projectId: ID!, $contentId: ID!) {
    addProjectV2ItemById(input: {projectId: $projectId, contentId: $contentId}) {
      item { id }
    }
  }' -f projectId="$PROJECT_ID" -f contentId="$ISSUE_NODE_ID"
```

This step is best-effort — if it fails (permissions, no project), log a warning and continue.

## Phase 5: Output

Print:
```
Issue:    https://github.com/<owner>/<repo>/issues/<N>
Assigned: @<user>
Labels:   <labels or "none">
Project:  <project name or "none">
Artifacts: <gist_url or "none">
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Creating duplicate issues | Always search for existing issue first (Phase 2a) |
| Overwriting existing issue title/body | Only update labels/assignee on existing issues, never overwrite content |
| Creating duplicate gist comments | Check for existing "Planning Artifacts" comment and replace it |
| Including README.md in planning artifacts | Exclude standard repo docs — only attach planning files |
| Using file paths instead of contents in gist | Gist must contain actual file contents for cross-machine access |
| Inventing requirements | Only include what the user described |
| Skipping project linking | Always attempt unless `--project=none` |
| Blocking on project link failure | Project linking is best-effort — create the issue regardless |
