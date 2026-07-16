from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.app import App
    from pilot.core.bench import Bench


class GetAppCommand(Command):
    name = "get-app"
    help = "Clone and install an app."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("repo", help="Git repository URL.")
        parser.add_argument("--branch", default="", help="Git branch to checkout.")
        parser.add_argument(
            "--install-dependencies",
            action="store_true",
            default=False,
            help="Install app dependencies",
        )
        parser.add_argument(
            "--skip-validations",
            action="store_true",
            default=False,
            help="Skip running app validations",
        )

    @classmethod
    def from_args(cls, args, bench):
        return cls(
            bench,
            args.repo,
            args.branch or "main",
            install_dependencies=args.install_dependencies,
            skip_validations=args.skip_validations,
        )

    def __init__(
        self,
        bench: "Bench",
        repo: str,
        branch: str = "",
        install_dependencies: bool = False,
        skip_validations: bool = False,
    ) -> None:
        from pathlib import PurePosixPath

        from pilot.config.app_config import AppConfig
        from pilot.core.app import App

        name = PurePosixPath(repo.rstrip("/")).name
        if name.endswith(".git"):
            name = name[:-4]

        if name.replace("-", "_").lower() == "frappe":
            from pilot.exceptions import BenchError

            raise BenchError(
                "'frappe' is the base framework, not an app — it can't be added "
                "with get-app. It's set up when the bench itself is created."
            )

        self.bench = bench
        self.repo = repo
        self.name = name
        self.install_dependencies = install_dependencies
        self.skip_validations = skip_validations
        self.app = App(AppConfig(name=name, repo=repo, branch=branch), bench)
        self._cloned_this_run = False
        self.installed_dependencies: list[App] = []

    def run(self) -> None:
        if self.bench.is_app_installed(self.name):
            self._update_installed_app_metadata()
            print(f"'{self.name}' already installed, skipping.")
            sys.stdout.flush()
            return

        self._clone()
        self._normalize_folder()

        if self.install_dependencies:
            self.installed_dependencies = self._install_dependencies()

        if not self.skip_validations:
            self._validate()

        self._install()
        self._register()
        self._build()
        print(f"\n'{self.name}' installed successfully.")

    def _update_installed_app_metadata(self) -> None:
        self.app = self.bench.app(self.app.module_name)
        self.name = self.app.config.name
        if self.install_dependencies:
            # Already installed — resolve its dependencies for the caller
            # (e.g. site installs), but never install anything for it.
            self.installed_dependencies = self._resolve_dependencies()

    def _clone(self) -> None:
        # is_cloned resolves the normalized (module-name) folder too, so a re-run
        # finds an existing clone however its folder was named.
        if self.app.is_cloned:
            print(f"'{self.name}' already cloned, skipping clone.")
            sys.stdout.flush()
            return
        print(f"Cloning {self.name}...")
        sys.stdout.flush()
        self.app.clone()
        self._cloned_this_run = True

    def _normalize_folder(self) -> None:
        module = self.app.module_name
        if module == self.app.config.name:
            return
        target = self.bench.apps_path / module
        # Rename a fresh clone into place; a prior run may have already normalized
        # it, in which case we just adopt the existing module-name folder.
        if not target.exists():
            self.app.path.rename(target)
        self._set_app(module)

    def _set_app(self, name: str) -> None:
        from pilot.config.app_config import AppConfig
        from pilot.core.app import App

        self.name = name
        self.app = App(
            AppConfig(name=name, repo=self.repo, branch=self.app.config.branch), self.bench
        )

    def _install_dependencies(self) -> list["App"]:
        import shutil

        from pilot.core.app_dependency_installer import AppDependencyInstaller
        from pilot.exceptions import BenchError

        try:
            return AppDependencyInstaller(self.bench, self.app).install()
        except BenchError:
            if self._cloned_this_run:
                shutil.rmtree(self.app.path, ignore_errors=True)
            raise

    def _resolve_dependencies(self) -> list["App"]:
        from pilot.core.app_dependency_installer import AppDependencyInstaller

        return AppDependencyInstaller(self.bench, self.app).resolve()

    def _install(self) -> None:
        from pilot.managers.python_env_manager import PythonEnvManager

        print(f"Installing {self.name}...")
        sys.stdout.flush()
        PythonEnvManager(self.bench).install_app(self.app)

    def _register(self) -> None:
        # apps.txt lists the importable package name; the folder was normalized to
        # that name in _normalize_folder, so self.name is it.
        existing = self.bench.registered_apps()
        if self.name not in existing:
            (self.bench.sites_path / "apps.txt").write_text(
                "\n".join(existing + [self.name]) + "\n"
            )

    def _validate(self) -> None:
        import shutil

        from pilot.core.app_validator import Validator
        from pilot.exceptions import AppValidationError

        try:
            Validator(self.app).validate()
        except AppValidationError:
            # Roll back the clone only if this run created it — an app that
            # was already installed (re-running get-app on it) must survive
            # a validation failure; only a fresh, unvetted clone gets removed.
            if self._cloned_this_run:
                shutil.rmtree(self.app.path, ignore_errors=True)
            raise

    def _build(self) -> None:
        from pilot.managers.python_env_manager import PythonEnvManager

        print(f"\nSetting up assets for {self.name}...")
        sys.stdout.flush()
        PythonEnvManager(self.bench).build_assets_for_app(self.app)
