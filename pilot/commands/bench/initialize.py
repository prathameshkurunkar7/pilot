from __future__ import annotations

from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class InitCommand(Command):
    name = "init"
    help = "Initialise the bench."
    # Heavy/irreversible — never guess the target bench.
    requires_explicit_bench = True

    def __init__(self, bench: "Bench") -> None:
        self.bench = bench

    def run(self) -> None:
        self.bench.initialize(on_progress=self.report)
