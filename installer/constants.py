from typing import Final

# One home for the installer's on-disk layout tokens, shared by the install/update
# composition layer: where units stage under the state root, and where skill
# sources live in the repo (~/.claude's per-kind dirs and the repo's skills/ tree).
STAGED_DIRNAME: Final[str] = "staged"
SKILLS_DIRNAME: Final[str] = "skills"
AGENTS_DIRNAME: Final[str] = "agents"
RULES_DIRNAME: Final[str] = "rules"
