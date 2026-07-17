from __future__ import annotations

import pytest

from pilot.commands.base import Command
from pilot.exceptions import BenchError


def test_report_prints_message(capsys: pytest.CaptureFixture) -> None:
    Command().print("hello")
    assert capsys.readouterr().out == "hello\n"


def test_confirm_skips_when_requested() -> None:
    Command().confirm("Proceed?", skip=True)  # no raise, no input


def test_confirm_raises_on_negative_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(BenchError, match="Aborted"):
        Command().confirm("Proceed?")


def test_confirm_passes_on_yes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("builtins.input", lambda _: "yes")
    Command().confirm("Proceed?")  # no raise


def test_confirm_raises_custom_error_type(monkeypatch: pytest.MonkeyPatch) -> None:
    class CustomError(Exception):
        pass

    monkeypatch.setattr("builtins.input", lambda _: "n")
    with pytest.raises(CustomError, match="Aborted"):
        Command().confirm("Proceed?", error=CustomError)


@pytest.mark.parametrize("exception", [EOFError, KeyboardInterrupt])
def test_confirm_treats_eof_and_ctrl_c_as_decline(monkeypatch: pytest.MonkeyPatch, exception: type[BaseException]) -> None:
    def raise_exception(_prompt: str) -> str:
        raise exception

    monkeypatch.setattr("builtins.input", raise_exception)
    with pytest.raises(BenchError, match="Aborted"):
        Command().confirm("Proceed?")
