import pytest
from pytest import CaptureFixture, MonkeyPatch

from at import main


def test_version_flag_prints_version_and_exits_zero(
    capsys: CaptureFixture[str],
) -> None:
    exit_code: int = main(["--version"])

    captured: str = capsys.readouterr().out
    assert captured == "at 0.2.0\n"
    assert exit_code == 0


@pytest.mark.parametrize("help_flag", ["--help", "-h"])
def test_help_flag_lists_subcommands_and_exits_zero(
    help_flag: str, capsys: CaptureFixture[str]
) -> None:
    exit_code: int = main([help_flag])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert "usage" in captured.lower()
    assert "install" in captured


def test_unknown_arg_errors_with_exit_two(capsys: CaptureFixture[str]) -> None:
    exit_code: int = main(["bogus"])

    captured: str = capsys.readouterr().err
    lowered: str = captured.lower()
    assert exit_code == 2
    assert captured != ""
    assert "bogus" in captured or "error" in lowered or "unknown" in lowered
    assert "--help" in captured or "usage" in lowered


def test_install_on_non_tty_prints_notice_and_exits_without_hanging(
    monkeypatch: MonkeyPatch, capsys: CaptureFixture[str]
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    exit_code: int = main(["install"])

    captured: str = capsys.readouterr().out
    assert exit_code == 0
    assert "Agent Templates Installer" in captured
    assert "terminal" in captured.lower()
