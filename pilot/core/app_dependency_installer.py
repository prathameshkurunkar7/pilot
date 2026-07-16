"""Resolves and installs an app's marketplace dependencies onto a bench."""
from __future__ import annotations

import sys
from typing import TYPE_CHECKING

from pilot.core.marketplace import Marketplace, Resolver
from pilot.exceptions import BenchError

if TYPE_CHECKING:
    from pilot.core.app import App
    from pilot.core.bench import Bench


class AppDependencyInstaller:
    """Installs whichever of an app's marketplace dependencies are missing
    from the bench, and reports every dependency App — fresh or already
    installed from an earlier run — so callers can install them onto
    requested sites too."""

    def __init__(self, bench: "Bench", app: "App") -> None:
        self.bench = bench
        self.app = app

    def install(self) -> list["App"]:
        resolver = self._find_resolver()
        if resolver is None:
            return []
        self._install_missing(resolver)
        return self._dependency_apps(resolver)

    def resolve(self) -> list["App"]:
        """List this app's dependencies without installing anything — for an
        already-installed app, whose dependencies must already be present
        too (installed together in an earlier run)."""
        resolver = self._find_resolver()
        if resolver is None:
            return []
        return self._dependency_apps(resolver)

    def _find_resolver(self) -> Resolver | None:
        try:
            return Marketplace(self.bench).find_app(self.app.config.name)
        except BenchError:
            # The app itself isn't in the marketplace registry — only a
            # problem if it actually declares dependencies we can't resolve.
            missing = self._missing_required_apps()
            if missing:
                raise BenchError(
                    f"'{self.app.config.name}' isn't in the marketplace registry, so its "
                    f"dependencies can't be installed automatically. It requires {missing} "
                    "— run 'bench get-app <repo>' for each of them first, then retry."
                )
            return None

    def _install_missing(self, resolver: Resolver) -> None:
        if all(self.bench.is_app_installed(dep) for dep in resolver.dependencies):
            return

        from pilot.commands.get_app import GetAppCommand

        try:
            dependency_chain = resolver.resolve()
        except BenchError as exc:
            raise BenchError(
                f"Could not resolve dependencies for '{self.app.config.name}':\n{exc}\n"
                "Manually install the dependencies before retrying."
            ) from exc

        for dep in dependency_chain[:-1]:  # exclude self (last entry)
            if dep.app == "frappe" or self.bench.is_app_installed(dep.app):
                continue
            print(f"Installing dependency '{dep.app}'...")
            sys.stdout.flush()
            # resolve() already returned the full transitive chain, so this
            # dependency's own deps are already installed by earlier entries.
            # Only the app the user actually asked for gets validated — a
            # dependency just needs to be installed, not vetted on its own.
            GetAppCommand(
                self.bench, dep.repo, dep.target, install_dependencies=False, skip_validations=True
            ).run()

    def _dependency_apps(self, resolver: Resolver) -> list["App"]:
        try:
            chain = resolver.resolve()
        except BenchError:
            return []

        apps = []
        for dep in chain[:-1]:  # exclude self (last entry)
            if dep.app == "frappe":
                continue
            try:
                apps.append(self.bench.app(dep.app))
            except BenchError:
                continue
        return apps

    def _missing_required_apps(self) -> list[str]:
        from pilot.core.app_validator.dependency_declarations import DependencyDeclarationsCheck

        required = DependencyDeclarationsCheck()._get_pyproject_required_apps(self.app)
        return [name for name in required if not self.bench.is_app_installed(name)]
