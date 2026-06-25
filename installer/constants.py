from typing import Final

# One home for the installer's on-disk layout tokens, shared by the install/update
# composition layer: where units stage under the state root, and where skill
# sources live in the repo (~/.claude's per-kind dirs and the repo's skills/ tree).
STAGED_DIRNAME: Final[str] = "staged"
SKILLS_DIRNAME: Final[str] = "skills"
AGENTS_DIRNAME: Final[str] = "agents"
RULES_DIRNAME: Final[str] = "rules"
HOOKS_DIRNAME: Final[str] = "hooks"

# Requester token marking a unit the user installed directly, outside any package.
# Seeded by install_package when it adopts a pre-existing bare direct install (a
# direct install_skill/etc. records no token of its own), so a later package
# uninstall leaves this marker behind and keeps a unit the user still wants. The
# leading "@" can never collide with a real package name, which is a bare catalog
# identifier, so the marker never clashes with an actual requester.
DIRECT_REQUESTER: Final[str] = "@direct"
