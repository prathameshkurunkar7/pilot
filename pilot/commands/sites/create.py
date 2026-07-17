from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

from pilot.commands.base import Command
from pilot.exceptions import BenchError

if TYPE_CHECKING:
    from pilot.core.bench import Bench
    from pilot.core.site import Site


class NewSiteCommand(Command):
    name = "new-site"
    help = "Create a new site and add it to bench.toml."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name", help="Site name (e.g. site2.localhost).")
        parser.add_argument("--admin-password", default="admin", help="Frappe admin password.")
        parser.add_argument("--apps", nargs="*", help="Apps to assign (defaults to framework app).")

    @classmethod
    def from_args(cls, args, bench):
        app_names = args.apps
        if not app_names:
            framework = bench.config.framework_app.name
            app_names = [framework] if framework else []
        return cls(bench, args.name, app_names, args.admin_password)

    def __init__(self, bench: "Bench", name: str, apps: list[str], admin_password: str, db_type: str | None = None) -> None:
        if not isinstance(admin_password, str) or not admin_password.strip():
            raise BenchError("Site Administrator password must not be empty.")
        self.bench = bench
        self.name = name  # type: ignore[misc]  # the new site's name, distinct from Command.name (the CLI verb)
        self.apps = apps
        self.admin_password = admin_password
        self.db_type = db_type
        self.site: "Site | None" = None

    def run(self) -> None:
        from pilot.core.site import Site

        self.site = Site.provision(
            self.bench, self.name, self.apps, self.admin_password, db_type=self.db_type, on_progress=self.print
        )
