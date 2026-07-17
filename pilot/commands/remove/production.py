from __future__ import annotations

from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class RemoveProductionCommand(Command):
    name = "production"
    help = "Remove a production deployment (keeps logs, certificates, admin domain)."
    group = "remove"

    def __init__(self, bench: "Bench") -> None:
        self.bench = bench

    def run(self) -> None:
        self.bench.remove_production(on_progress=self.report)
