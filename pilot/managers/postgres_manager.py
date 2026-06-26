from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

from bench_cli.config.postgres_config import PostgresConfig
from bench_cli.platform import (
    _privileged,
    get_package_manager,
    is_alpine,
    is_linux,
    is_macos,
    service_command,
    service_enable_command,
    service_running,
    which,
)
from bench_cli.utils import run_command

DEFAULT_VERSION = "16"
_SERVICE = "postgresql"


class PostgresManager:
    """Manage the shared system PostgreSQL bench installs and provisions.

    Unlike MariaDB, there are no per-bench instances — benches share one server
    and are isolated at the database level (frappe creates one db per site).
    """

    def __init__(self, config: PostgresConfig) -> None:
        self.config = config

    # ── install ──────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return bool(which("psql") or which("postgres") or which("initdb"))

    def install(self) -> None:
        if self.is_installed():
            return
        if is_macos():
            get_package_manager().install(self._brew_package())
            return
        get_package_manager().install("postgresql", "postgresql-client")

    def _version(self) -> str:
        return self.config.version or DEFAULT_VERSION

    def _brew_package(self) -> str:
        return self._installed_brew_formula() or f"postgresql@{self._version()}"

    def _installed_brew_formula(self) -> str | None:
        """The postgresql formula Homebrew already manages, so start/stop target
        whatever is installed rather than assuming a version."""
        result = subprocess.run(["brew", "list", "--formula"], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        formulae = result.stdout.split()
        if "postgresql" in formulae:
            return "postgresql"
        return next((f for f in formulae if f.startswith("postgresql@")), None)

    # ── service control ──────────────────────────────────────────────────────

    def is_running(self) -> bool:
        return self._brew_service_running() if is_macos() else service_running(_SERVICE)

    def start(self) -> None:
        if is_macos():
            run_command(["brew", "services", "start", self._brew_package()])
        else:
            run_command(service_command("start", _SERVICE))

    def restart(self) -> None:
        if is_macos():
            run_command(["brew", "services", "restart", self._brew_package()])
        else:
            run_command(service_command("restart", _SERVICE))

    def enable(self) -> None:
        # `brew services start` already persists across logins.
        if is_macos():
            return
        try:
            run_command(service_enable_command(_SERVICE))
        except Exception:
            pass

    def _brew_service_running(self) -> bool:
        result = subprocess.run(["brew", "services", "list"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts and parts[0] == self._brew_package() and "started" in parts:
                return True
        return False

    # ── provisioning ─────────────────────────────────────────────────────────

    def provision(self) -> None:
        """Install, start, enable and secure the server. Idempotent — safe to re-run."""
        self.install()
        if is_alpine():
            self._ensure_alpine_cluster()
        self.enable()
        if not self.is_running():
            self.start()
        self._wait_until_reachable()
        self.secure()

    def secure(self) -> None:
        """Ensure the admin role exists with the configured password so frappe can
        connect over TCP. Idempotent: a no-op once credentials work."""
        if not self.config.root_password:
            print(
                "  postgres.root_password is empty — skipping superuser setup. "
                "Set it in Settings before creating PostgreSQL sites."
            )
            return
        if self.check_credentials():
            return
        self._run_sql_as_superuser(self._ensure_role_sql())
        if not self.check_credentials():
            raise RuntimeError(
                f"PostgreSQL is installed but bench could not authenticate as '{self.config.admin_user}' "
                "over TCP. Ensure the server's pg_hba.conf allows password auth from localhost, or set "
                "postgres.root_password to the existing superuser password."
            )

    def check_credentials(self, password: str | None = None) -> bool:
        """True if the admin user can connect over TCP with the given password
        (default: configured root password). Uses psql so the zero-dep CLI works
        during init; the password goes via PGPASSWORD, not argv."""
        pw = self.config.root_password if password is None else password
        psql = self._psql()
        if not psql:
            return False
        cmd = [psql, "-h", self.config.host, "-p", str(self.config.port), "-U", self.config.admin_user, "-d", "postgres", "-tAc", "SELECT 1"]
        result = subprocess.run(cmd, env={**os.environ, "PGPASSWORD": pw}, capture_output=True, text=True)
        return result.returncode == 0

    def _ensure_role_sql(self) -> str:
        role = self._quote_ident(self.config.admin_user)
        name = self._sql_quote(self.config.admin_user)
        pw = self._sql_quote(self.config.root_password)
        return (
            "DO $$ BEGIN "
            f"IF EXISTS (SELECT FROM pg_roles WHERE rolname = {name}) THEN "
            f"ALTER ROLE {role} WITH LOGIN SUPERUSER PASSWORD {pw}; "
            "ELSE "
            f"CREATE ROLE {role} WITH LOGIN SUPERUSER PASSWORD {pw}; "
            "END IF; END $$;"
        )

    def _run_sql_as_superuser(self, sql: str) -> None:
        # The bootstrap superuser is the `postgres` OS account on Linux (peer auth
        # over the local socket) and the current user on macOS (Homebrew).
        cmd = ["sudo", "-u", "postgres", "psql"] if is_linux() else [self._psql() or "psql"]
        cmd += ["-v", "ON_ERROR_STOP=1", "-d", "postgres"]
        subprocess.run(cmd, input=sql, text=True, check=True)

    def _wait_until_reachable(self, timeout: float = 30.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._accepting_connections():
                return
            time.sleep(0.5)

    def _accepting_connections(self) -> bool:
        ready = which("pg_isready")
        if ready:
            result = subprocess.run([ready, "-h", self.config.host, "-p", str(self.config.port)], capture_output=True)
            return result.returncode == 0
        return self.is_running()

    def _ensure_alpine_cluster(self) -> None:
        """apk neither initialises the data dir nor enables the service.
        Initialise the default cluster once; safe to re-run. Best-effort: assumes
        the conventional /var/lib/postgresql/<version>/data layout."""
        data_dir = Path(f"/var/lib/postgresql/{self._version()}/data")
        if (data_dir / "PG_VERSION").exists():
            return
        run_command(_privileged(["install", "-d", "-m", "700", "-o", "postgres", "-g", "postgres", str(data_dir)]))
        run_command(["sudo", "-u", "postgres", "initdb", "-D", str(data_dir)])

    def _psql(self) -> str | None:
        found = which("psql")
        if found:
            return found
        if is_macos():
            result = subprocess.run(["brew", "--prefix", self._brew_package()], capture_output=True, text=True)
            if result.returncode == 0:
                candidate = Path(result.stdout.strip()) / "bin" / "psql"
                if candidate.exists():
                    return str(candidate)
        return None

    @staticmethod
    def _sql_quote(value: str) -> str:
        """Quote a value as a PostgreSQL string literal."""
        return "'" + value.replace("'", "''") + "'"

    @staticmethod
    def _quote_ident(value: str) -> str:
        """Quote an identifier (role name)."""
        return '"' + value.replace('"', '""') + '"'
