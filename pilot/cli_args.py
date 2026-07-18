from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Arg:
    help: str = ""
    short: str | None = None
    cli: bool = True
    metavar: str | None = None
    required: bool = False
