---
name: issue-create
description: Use when the user wants to create a GitHub issue and optionally link it to a project, or invokes /issue-create.
---

# Issue Create

Create a GitHub issue for the current repository and link it to a GitHub Project.

```
/issue-create [--title="..."] [--labels=bug,enhancement] [--assignee=@me] [--project="..."]

  1. Gather repo info
  2. Build issue title and body from user input or conversation context
  3. Create the issue
  4. Link to a GitHub Project (auto-detect or explicit)
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

Parse arguments from the user's message. All are optional:

| Arg | Default | Example |
|-----|---------|---------|
| `--title="..."` | Generated from conversation context | `--title="Fix auth timeout"` |
| `--labels=l1,l2` | None | `--labels=bug,P1` |
| `--assignee=user` | `@me` | `--assignee=alice` |
| `--project="..."` | Auto-detect | `--project="Backend"` |
| `--milestone="..."` | None | `--milestone="v2.1"` |

## Phase 1: Gather Info

Run in parallel:

```bash
OWNER=$(gh repo view --json owner -q '.owner.login')
REPO=$(gh repo view --json name -q '.name')
CURRENT_USER=$(gh api user -q '.login')
```

## Phase 2: Build Issue Content

### Title

Use `--title` if provided. Otherwise, derive from the conversation context:
- If the user described a bug or feature, summarize it in under 70 characters
- If a plan.md exists and the user referenced it, use the first heading

### Body

Build the body from the user's description. Structure it as:

```markdown
## Description

<User's description or conversation context summarized clearly>

## Acceptance Criteria

- [ ] <derived from the user's request>
```

If the user provided a detailed description, use it directly. If they gave a brief request, expand it into a clear description. Do not invent requirements the user didn't mention.

## Phase 3: Create Issue

```bash
gh issue create \
  --title "$ISSUE_TITLE" \
  --body "$ISSUE_BODY" \
  --assignee "${ARG_ASSIGNEE:-@me}" \
  ${LABELS:+--label "$LABELS"} \
  ${MILESTONE:+--milestone "$MILESTONE"}
```

Extract the issue number from the output.

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
```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Inventing requirements the user didn't ask for | Only include what the user described — don't add extra acceptance criteria |
| Skipping project linking | Always attempt project linking unless `--project=none` |
| Title too long | Keep under 70 characters |
| Not assigning | Default to `@me` if no assignee specified |
| Blocking on project link failure | Project linking is best-effort — create the issue regardless |
