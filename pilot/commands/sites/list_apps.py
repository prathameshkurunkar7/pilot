from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class ListSiteAppsCommand(Command):
    name = "list-site-apps"
    help = "List apps installed on a site."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("site", help="Site name (e.g. site1.localhost).")

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, args.site)

    def __init__(self, bench: "Bench", site_name: str) -> None:
        from pilot.config.site import SiteConfig
        from pilot.core.site import Site

        self.bench = bench
        self.site_name = site_name
        self.site = Site(SiteConfig(name=site_name, apps=[]), bench)

    def run(self) -> None:
        for app in self.site.installed_apps():
            self.print(app)
