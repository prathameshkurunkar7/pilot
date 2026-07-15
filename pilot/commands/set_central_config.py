from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import TYPE_CHECKING

from pilot.commands.base import Command
from pilot.exceptions import BenchError

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class SetCentralConfigCommand(Command):
    """Persist the Central callback endpoint + pilot auth token that Atlas hands the
    bench at deploy, so pilot→Central calls can authenticate. Merges into
    bench.toml (bench-owned config) without disturbing the other sections."""

    name = "set-central-config"
    help = "Store the Central endpoint + pilot auth token in bench.toml."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--endpoint", required=True, help="Central API base URL the pilot calls back on")
        parser.add_argument("--token-file", help="File containing the Central authentication token")

    @classmethod
    def from_args(cls, args, bench):
        token = os.environ.get("BENCH_CENTRAL_TOKEN", "")
        if args.token_file:
            token = Path(args.token_file).read_text().strip()
        if not token:
            raise BenchError("Set BENCH_CENTRAL_TOKEN or pass --token-file.")
        return cls(bench, endpoint=args.endpoint, token=token)

    def __init__(self, bench: "Bench", endpoint: str, token: str) -> None:
        self.bench = bench
        self.endpoint = endpoint
        self.token = token

    def run(self) -> None:
        from pilot.config.toml_store import BenchTomlStore

        store = BenchTomlStore.for_bench(self.bench.path)
        try:
            with store.edit_raw() as config:
                config.setdefault("central", {})["endpoint"] = self.endpoint
                config["central"]["auth_token"] = self.token
        except FileNotFoundError as exc:
            raise BenchError(f"{store.path} not found — is this a bench?") from exc
        except ValueError as exc:
            raise BenchError(f"{store.path} contains invalid TOML: {exc}") from exc
        self.bench.config.central.endpoint = self.endpoint
        self.bench.config.central.auth_token = self.token
        print("Central config written to bench.toml")
