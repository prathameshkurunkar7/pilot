from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class UninstallAppCommand(Command):
    name = "uninstall-app"
    help = "Uninstall one or more apps from a site, also remove app from bench if not installed on any site"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("site", help="Site name.")
        parser.add_argument("apps", nargs="+", help="App name(s) to uninstall.")
        parser.add_argument(
            "--force", action="store_true", help="Uninstall even if not tracked as installed."
        )

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, args.site, args.apps, force=args.force)

    def __init__(
        self, bench: "Bench", site_name: str, app_names: list[str], force: bool = False
    ) -> None:
        from pilot.config.site import SiteConfig
        from pilot.core.site import Site

        self.bench = bench
        self.site_name = site_name
        self.app_names = app_names
        self.force = force
        self.site = Site(SiteConfig(name=site_name, apps=[]), bench)

    def run(self) -> None:
        self.site.uninstall_apps(self.app_names, force=self.force, on_progress=self.print)
