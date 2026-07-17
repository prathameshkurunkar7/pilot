from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class RemoveAppCommand(Command):
    name = "remove-app"
    help = "Remove an app from the bench."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("app", help="App name to remove.")

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, args.app, skip_confirm=args.yes)

    def __init__(self, bench: "Bench", app_name: str, skip_confirm: bool = False, force: bool = False) -> None:
        self.bench = bench
        self.app_name = app_name
        self.skip_confirm = skip_confirm
        self.force = force
        self.app = bench.app(app_name)

    def run(self) -> None:
        self.app.ensure_removable()
        self.confirm(f"Remove '{self.app_name}' from all sites and the bench?", skip=self.skip_confirm)
        self.app.remove(force=self.force, on_progress=self.print)
