from __future__ import annotations

import argparse
import shutil
from typing import TYPE_CHECKING

from pilot.commands.base import Command
from pilot.exceptions import BenchError

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
        self.app_path = bench.apps_path / app_name

    def run(self) -> None:
        self._validate()
        self.confirm(f"Remove '{self.app_name}' from all sites and the bench?", skip=self.skip_confirm)
        self._uninstall_from_sites()
        self._remove_from_apps_txt()
        self._pip_uninstall()
        self._delete_app_dir()
        self.report(f"\n'{self.app_name}' removed from bench.")

    def _validate(self) -> None:
        if not self.app_path.exists():
            raise BenchError(f"App '{self.app_name}' not found in bench.")
        framework = self.bench.config.framework_app.name
        if self.app_name == framework:
            raise BenchError(f"Cannot remove the framework app '{framework}'.")

    def _uninstall_from_sites(self) -> None:
        for site in self.bench.sites():
            installed = site.list_apps()
            if self.app.config.name in installed:
                self.report(f"Uninstalling '{self.app_name}' from site '{site.config.name}'...")
                try:
                    site.uninstall_app(self.app, force=self.force)
                except Exception as e:
                    if self.force:
                        self.report(f"Warning: could not cleanly uninstall from '{site.config.name}': {e}")
                    else:
                        raise

    def _remove_from_apps_txt(self) -> None:
        apps_txt = self.bench.sites_path / "apps.txt"
        if not apps_txt.exists():
            return
        lines = [
            line for line in apps_txt.read_text().splitlines()
            if line.strip() != self.app_name
        ]
        apps_txt.write_text("\n".join(lines) + ("\n" if lines else ""))

    def _pip_uninstall(self) -> None:
        from pilot.managers.python_environment import PythonEnvManager

        self.report(f"Removing '{self.app_name}' from Python environment...")
        PythonEnvManager(self.bench).uninstall_app(self.app_name)

    def _delete_app_dir(self) -> None:
        self.report(f"Deleting {self.app_path}...")
        shutil.rmtree(self.app_path)
