from __future__ import annotations

import argparse
import json
from typing import TYPE_CHECKING

from pilot.commands.base import Command
from pilot.exceptions import BenchError

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class SetCentralConfigCommand(Command):
    """Persist the Central callback endpoint + pilot auth token that Atlas hands the
    bench at deploy, so pilot→Central calls can authenticate. Merges into
    common_site_config (bench-wide) without disturbing the other keys."""

    name = "set-central-config"
    help = "Store the Central endpoint + pilot auth token in common_site_config."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--endpoint", required=True, help="Central API base URL the pilot calls back on")
        parser.add_argument("--token", required=True, help="Opaque token the pilot presents to Central")

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, endpoint=args.endpoint, token=args.token)

    def __init__(self, bench: "Bench", endpoint: str, token: str) -> None:
        self.bench = bench
        self.endpoint = endpoint
        self.token = token

    def run(self) -> None:
        config_path = self.bench.sites_path / "common_site_config.json"
        try:
            config = json.loads(config_path.read_text())
        except FileNotFoundError as exc:
            raise BenchError(f"{config_path} not found — is this a bench?") from exc
        config["central_endpoint"] = self.endpoint
        config["central_auth_token"] = self.token
        config_path.write_text(json.dumps(config, indent=2) + "\n")
        print("Central config written to common_site_config.json")
