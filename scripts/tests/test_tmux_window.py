"""Tests for the tmux window helper, driven against a real tmux server.

Each test runs its own tmux server on a private socket, so a run never touches the
default server the user sits in.
"""

from __future__ import annotations

import subprocess
import uuid
from collections.abc import Iterator
from typing import Final

import pytest

from at_pr.tmux_window import TmuxServer

TMUX: Final[str] = "tmux"
SESSION_NAME: Final[str] = "at-pr-tests"
WINDOW_NAME: Final[str] = "at-pr-probe"
LISTING_FORMAT: Final[str] = "#{window_id} #{window_name}"


@pytest.fixture
def private_socket() -> Iterator[str]:
    """The socket of a tmux server started for one test and killed after it."""
    socket: str = f"at-pr-{uuid.uuid4().hex}"
    start: tuple[str, ...] = (
        TMUX,
        "-L",
        socket,
        "new-session",
        "-d",
        "-s",
        SESSION_NAME,
    )
    subprocess.run(start, check=True)
    try:
        yield socket
    finally:
        kill: tuple[str, ...] = (TMUX, "-L", socket, "kill-server")
        subprocess.run(kill, check=True)


@pytest.fixture
def tmux_server(private_socket: str) -> TmuxServer:
    return TmuxServer(socket=private_socket)


def window_listing(*, socket: str) -> frozenset[str]:
    """Every window the tmux server holds, one `<window id> <window name>` line each."""
    command: tuple[str, ...] = (
        TMUX,
        "-L",
        socket,
        "list-windows",
        "-a",
        "-F",
        LISTING_FORMAT,
    )
    listed: subprocess.CompletedProcess[str] = subprocess.run(
        command, check=True, capture_output=True, text=True
    )
    return frozenset(listed.stdout.splitlines())


def test_open_window_makes_a_live_window_under_the_given_name(
    tmux_server: TmuxServer, private_socket: str
) -> None:
    window_id: str = tmux_server.open_window(name=WINDOW_NAME)

    assert tmux_server.window_exists(window_id=window_id)
    listing: frozenset[str] = window_listing(socket=private_socket)
    assert f"{window_id} {WINDOW_NAME}" in listing


def test_kill_window_closes_an_open_window(tmux_server: TmuxServer) -> None:
    window_id: str = tmux_server.open_window(name=WINDOW_NAME)

    tmux_server.kill_window(window_id=window_id)

    assert not tmux_server.window_exists(window_id=window_id)


def test_kill_window_on_a_missing_window_is_a_no_op(tmux_server: TmuxServer) -> None:
    window_id: str = tmux_server.open_window(name=WINDOW_NAME)
    tmux_server.kill_window(window_id=window_id)

    tmux_server.kill_window(window_id=window_id)

    assert not tmux_server.window_exists(window_id=window_id)
