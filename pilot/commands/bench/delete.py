from __future__ import annotations

from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class DropBenchCommand(Command):
    name = "drop"
    help = "Delete a bench (must have no sites), tearing down its production services and nginx."
    # Deleting whichever bench happens to be active by default would be too easy
    # to trigger by accident, so require an explicit -b/--bench (or running from
    # inside the bench dir).
    requires_explicit_bench = True

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, skip_confirm=args.yes)

    def __init__(self, bench: "Bench", skip_confirm: bool = False) -> None:
        self.bench = bench
        self.skip_confirm = skip_confirm

    def run(self) -> None:
        self.bench.ensure_no_sites()
        self.confirm(
            f"Permanently delete bench '{self.bench.config.name}' and its database?",
            skip=self.skip_confirm,
        )
        self.bench.drop(on_progress=self.report)
