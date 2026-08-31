"""Windows on a tmux server, driven by the tmux binary rather than a tmux library."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from typing import Final

TMUX: Final[str] = "tmux"
WINDOW_ID_FORMAT: Final[str] = "#{window_id}"


@dataclass(frozen=True)
class TmuxServer:
    """One tmux server, addressed by its socket name; the default server when None."""

    socket: str | None = None

    def open_window(self, *, name: str) -> str:
        """Open a detached window under the given name and return its tmux window id."""
        arguments: tuple[str, ...] = (
            "new-window",
            "-d",
            "-P",
            "-F",
            WINDOW_ID_FORMAT,
            "-n",
            name,
        )
        opened: str = self._run(arguments=arguments)
        return opened.strip()

    def window_exists(self, *, window_id: str) -> bool:
        """Whether a window with that id is live in any session on this server."""
        arguments: tuple[str, ...] = ("list-windows", "-a", "-F", WINDOW_ID_FORMAT)
        listed: str = self._run(arguments=arguments)
        window_ids: frozenset[str] = frozenset(listed.splitlines())
        return window_id in window_ids

    def kill_window(self, *, window_id: str) -> None:
        """Close the window with that id."""
        arguments: tuple[str, ...] = ("kill-window", "-t", window_id)
        self._run(arguments=arguments)

    def _run(self, *, arguments: tuple[str, ...]) -> str:
        """Run tmux against this server with these arguments and return its stdout."""
        socket_flag: tuple[str, ...] = (
            () if self.socket is None else ("-L", self.socket)
        )
        argv: tuple[str, ...] = (TMUX, *socket_flag, *arguments)
        completed: subprocess.CompletedProcess[str] = subprocess.run(
            argv, check=True, capture_output=True, text=True
        )
        return completed.stdout
