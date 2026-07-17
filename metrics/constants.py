from typing import Final

# A usage-bearing line's `attributionAgent` names the subagent role it belongs to;
# a main-transcript line carries none, so its usage is attributed to the run itself.
MAIN_ROLE: Final[str] = "main"
