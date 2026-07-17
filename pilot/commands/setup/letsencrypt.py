from __future__ import annotations

from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class SetupLetsEncryptCommand(Command):
    name = "letsencrypt"
    help = "Setup Let's Encrypt SSL."
    group = "setup"

    def __init__(self, bench: "Bench") -> None:
        self.bench = bench

    def run(self) -> None:
        self.bench.setup_letsencrypt()
