from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from bench_cli.config.site_config import SiteConfig
from bench_cli.utils import run_command

if TYPE_CHECKING:
    from bench_cli.core.app import App
    from bench_cli.core.bench import Bench


class Site:
    def __init__(self, config: SiteConfig, bench: "Bench", database_engine: str | None = None) -> None:
        self.config = config
        self.bench = bench
        self.database_engine = database_engine or bench.config.database_engine

    @property
    def path(self) -> Path:
        return self.bench.sites_path / self.config.name

    @property
    def exists(self) -> bool:
        return (self.path / "site_config.json").exists()

    def _frappe_call(self, *args: str) -> list[str]:
        """Build a frappe bench_helper command."""
        return [*self.bench.frappe_call, *args]

    def create(self) -> None:
        from bench_cli.managers.database_manager import create_database_manager

        manager = create_database_manager(self._config_for_engine())

        cmd = self._frappe_call(
            "frappe",
            "--site",
            self.config.name,
            "new-site",
            self.config.name,
            "--db-type",
            self.database_engine,
            "--admin-password",
            self.config.admin_password,
        )
        if self.database_engine == "sqlite":
            run_command(cmd, cwd=self.bench.sites_path, stream_output=True)
            return

        database = self.bench.config.postgres if self.database_engine == "postgres" else self.bench.config.mariadb
        cmd += ["--db-root-username", database.admin_user]
        if self.database_engine == "mariadb" and (socket_path := manager._detect_socket()):
            cmd += ["--db-socket", socket_path]
            # unix_socket auth ignores the password; pass a non-empty placeholder
            # so frappe doesn't fall back to an interactive getpass() prompt
            cmd += ["--db-root-password", database.root_password or "socket_auth"]
        else:
            host = database.socket_path or database.host if self.database_engine == "postgres" else database.host
            cmd += ["--db-host", host, "--db-port", str(database.port)]
            if database.root_password:
                cmd += ["--db-root-password", database.root_password]

        run_command(cmd, cwd=self.bench.sites_path, stream_output=True)

    def restore(self, db_file: str, public_files: str | None = None, private_files: str | None = None) -> None:
        cmd = self._frappe_call("frappe", "--site", self.config.name, "restore", db_file)
        if public_files:
            cmd += ["--with-public-files", public_files]
        if private_files:
            cmd += ["--with-private-files", private_files]

        if self.database_engine != "sqlite":
            database = self.bench.config.postgres if self.database_engine == "postgres" else self.bench.config.mariadb
            cmd += ["--db-root-username", database.admin_user, "--db-root-password", database.root_password]

        run_command(cmd, cwd=self.bench.sites_path, stream_output=True)

    def _config_for_engine(self):
        """Select a manager without mutating the bench-wide default engine."""
        if self.database_engine == self.bench.config.database_engine:
            return self.bench.config
        from dataclasses import replace
        return replace(self.bench.config, database_engine=self.database_engine)

    def install_app(self, app: "App") -> None:
        run_command(
            self._frappe_call("frappe", "--site", self.config.name, "install-app", app.config.name),
            cwd=self.bench.sites_path,
            stream_output=True,
        )
        self.bench.reload_workers(raises=True)

    def uninstall_app(self, app: "App", force: bool = False) -> None:
        cmd = self._frappe_call("frappe", "--site", self.config.name, "uninstall-app", app.config.name, "--yes", "--no-backup")
        if force:
            cmd.append("--force")
        run_command(cmd, cwd=self.bench.sites_path, stream_output=True)
        self.bench.reload_workers(raises=True)

    def list_apps(self) -> list[str]:
        import subprocess

        result = subprocess.run(
            self._frappe_call("frappe", "--site", self.config.name, "list-apps"),
            cwd=str(self.bench.sites_path),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            return []
        return [line.split()[0] for line in result.stdout.splitlines() if line.strip()]

    def migrate(self) -> None:
        run_command(
            self._frappe_call("frappe", "--site", self.config.name, "migrate"),
            cwd=self.bench.sites_path,
            stream_output=True,
        )
