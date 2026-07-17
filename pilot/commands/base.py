from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING, ClassVar, Optional

from pilot.exceptions import BenchError

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class Command:
    """Base class for self-registering CLI commands. The registry discovers
    every subclass that sets a ``name`` and wires it into the parser."""

    #: CLI name, e.g. "remove-app". Subclasses without a name are not registered.
    name: ClassVar[str]
    help: ClassVar[str] = ""
    #: Parent group for subcommands, e.g. "setup" (None = top level).
    group: ClassVar[Optional[str]] = None
    #: If True, the registry loads the selected Bench and passes it to from_args.
    requires_bench: ClassVar[bool] = True
    #: If True, pass the Bench when one resolves, else None (ignored if requires_bench).
    optional_bench: ClassVar[bool] = False
    #: If True, require -b/--bench or running inside the bench dir (no auto-pick).
    requires_explicit_bench: ClassVar[bool] = False
    #: If True, `-b all` runs this command once per production-managed bench.
    supports_all_benches: ClassVar[bool] = False

    def __init__(self, bench: "Bench | None" = None) -> None:
        self.bench = bench

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        """Override to declare this command's argparse arguments."""

    @classmethod
    def from_args(cls, args: argparse.Namespace, bench: "Bench | None") -> "Command":
        return cls(bench)

    def run(self) -> None:
        raise NotImplementedError

    def print(self, message: str) -> None:
        # Flushed immediately so it's visible before any subprocess output.
        print(message)
        sys.stdout.flush()

    def confirm(self, prompt: str, *, skip: bool = False, error: type[Exception] = BenchError) -> None:
        if skip:
            return
        try:
            answer = input(f"{prompt} [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer not in ("y", "yes"):
            raise error("Aborted.")
