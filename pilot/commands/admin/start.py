from __future__ import annotations

import argparse
from pathlib import Path

from pilot.commands.base import Command


def download_admin_frontend(cli_root: Path) -> bool:
    from pilot.core.admin_frontend import download_admin_frontend as _download

    return _download(cli_root)


class BuildAdminCommand(Command):
    name = "build-admin"
    help = "Download or rebuild admin frontend assets."
    requires_bench = False

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--force", action="store_true", help="Skip download and build from source.")

    @classmethod
    def from_args(cls, args, bench):
        return cls(force_build=args.force)

    def __init__(self, force_build: bool = False) -> None:
        self.force_build = force_build

    def run(self) -> None:
        from pilot.core.admin_frontend import build_admin_frontend

        build_admin_frontend(self.force_build, on_progress=self.print)
