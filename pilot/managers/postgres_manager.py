from __future__ import annotations

import os
import socket
import subprocess
import time
from pathlib import Path

from pilot.config.postgres_config import PostgresConfig
from pilot.package_managers import get_package_manager
from pilot.platform import (
    _privileged,
    is_alpine,
    is_macos,
    service_command,
    service_enable_command,
    service_running,
    which,
)
from pilot.utils import run_command

DEFAULT_VERSION = "16"

# One PostgreSQL server per bench user, shared by every bench they own —
# rootless, running as a single systemd --user unit. Fixed locations, no
# per-bench units.
_STATE_DIR = Path.home() / ".local" / "share" / "pilot" / "postgres"
_UNIT_NAME = "pilot-postgres.service"

# Alpine has no systemd --user equivalent, and Alpine containers commonly
# already run as root, so this one platform keeps using the conventional
# system-wide postgresql-<version> service instead of a per-user unit.
_ALPINE_DATA_DIR = Path(f"/var/lib/postgresql/{DEFAULT_VERSION}/data")
_ALPINE_SERVICE = "postgresql"


class PostgresManager:
    """Manage the single, per-bench-user PostgreSQL server. Every bench for a
    given OS user connects to the same running server (isolated per-database),
    provisioned once by whichever bench inits first."""

    def __init__(self, config: PostgresConfig) -> None:
        self.config = config

    def data_dir(self) -> Path:
        return _ALPINE_DATA_DIR if is_alpine() else _STATE_DIR / "data"

    # ── install ──────────────────────────────────────────────────────────────

    def is_installed(self) -> bool:
        return bool(which("psql") or which("postgres") or which("initdb"))

    def install(self) -> None:
        if self.is_installed():
            return
        if is_macos():
            get_package_manager().install(self._brew_package())
            return
        if is_alpine():
            # Alpine images commonly run as root already; _privileged() is a
            # no-op there, so installing here (rather than only via install.sh)
            # keeps root-in-container images working out of the box.
            get_package_manager().install(*self._alpine_packages())
            return
        raise RuntimeError(
            "PostgreSQL is not installed. Re-run install.sh as root to install "
            "it (it provisions postgresql for every supported distro), or "
            "install 'postgresql' yourself."
        )

    def _alpine_packages(self) -> list[str]:
        return [f"postgresql{DEFAULT_VERSION}", f"postgresql{DEFAULT_VERSION}-client"]

    def alpine_dev_package(self) -> str:
        """libpq build headers for psycopg — versioned on Alpine."""
        return f"postgresql{DEFAULT_VERSION}-dev"

    def _brew_package(self) -> str:
        return self._installed_brew_formula() or f"postgresql@{DEFAULT_VERSION}"

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

    def unit_path(self) -> Path:
        return self._user_unit_dir() / _UNIT_NAME

    def is_provisioned(self) -> bool:
        """The unit file existing is the single source of truth: once it's
        there, this server has already been set up (by this bench or a
        sibling) — reuse it rather than re-initialising."""
        return self.unit_path().exists()

    def is_running(self) -> bool:
        if is_macos():
            return self._brew_service_running()
        if is_alpine():
            return service_running(_ALPINE_SERVICE)
        result = subprocess.run(self._systemctl("is-active", _UNIT_NAME), env=self._systemctl_env(), capture_output=True)
        return result.returncode == 0

    def start(self) -> None:
        if is_macos():
            run_command(["brew", "services", "start", self._brew_package()])
        elif is_alpine():
            run_command(service_command("start", _ALPINE_SERVICE))
        else:
            run_command(self._systemctl("start", _UNIT_NAME), env=self._systemctl_env())

    def restart(self) -> None:
        if is_macos():
            run_command(["brew", "services", "restart", self._brew_package()])
        elif is_alpine():
            run_command(service_command("restart", _ALPINE_SERVICE))
        else:
            run_command(self._systemctl("restart", _UNIT_NAME), env=self._systemctl_env())

    def stop(self) -> None:
        if is_macos():
            run_command(["brew", "services", "stop", self._brew_package()])
        elif is_alpine():
            run_command(service_command("stop", _ALPINE_SERVICE))
        else:
            run_command(self._systemctl("stop", _UNIT_NAME), env=self._systemctl_env())

    def _brew_service_running(self) -> bool:
        result = subprocess.run(["brew", "services", "list"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts and parts[0] == self._brew_package() and "started" in parts:
                return True
        return False

    def _systemctl(self, *args: str) -> list[str]:
        return ["systemctl", "--user", *args]

    def _systemctl_env(self) -> dict:
        # A login session normally sets XDG_RUNTIME_DIR; environments without
        # one (CI runners, su -c) need it set explicitly for `systemctl --user`
        # to find the right user manager. Mirrors process_managers/systemd.py.
        env = dict(os.environ)
        if not env.get("XDG_RUNTIME_DIR"):
            env["XDG_RUNTIME_DIR"] = f"/run/user/{os.getuid()}"
        return env

    # ── provisioning ─────────────────────────────────────────────────────────

    def provision(self) -> None:
        """Install, start and secure the shared server. Idempotent — safe for
        every bench to call; the first bench for this user provisions it,
        later benches just reuse the already-running server."""
        self.install()
        if is_macos():
            if not self.is_running():
                self.start()
        elif is_alpine():
            self._provision_alpine()
        else:
            self._provision_user_owned()
        self._wait_until_reachable()
        self.secure()

    def _provision_user_owned(self) -> None:
        if not self.is_provisioned():
            self._ensure_port_available()
            self.data_dir().parent.mkdir(parents=True, exist_ok=True)
            # No --username: the bootstrap superuser matches whoever runs
            # initdb (the bench user), authenticated via unix-socket peer
            # auth — no sudo, no OS-level 'postgres' account involved.
            run_command(["initdb", "-D", str(self.data_dir())])
            self._install_unit()
            run_command(self._systemctl("enable", "--now", _UNIT_NAME), env=self._systemctl_env())
        elif not self.is_running():
            run_command(self._systemctl("start", _UNIT_NAME), env=self._systemctl_env())

    def _ensure_port_available(self) -> None:
        """Only checked before this server has ever been provisioned — once
        our unit owns the port, is_provisioned() short-circuits future calls,
        so this never fires again for that port."""
        try:
            with socket.create_connection(("127.0.0.1", self.config.port), timeout=0.3):
                pass
        except OSError:
            return  # nothing listening there — free to bind
        raise RuntimeError(
            f"Port {self.config.port} is already in use by another service "
            f"(e.g. a system-wide PostgreSQL). Free it, or set postgres.port in "
            f"bench.toml to an unused port, then retry."
        )

    def _install_unit(self) -> None:
        postgres = which("postgres") or "/usr/lib/postgresql/bin/postgres"
        content = (
            "[Unit]\n"
            "Description=PostgreSQL (pilot, user-owned)\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={postgres} -D {self.data_dir()} -p {self.config.port} "
            "-c listen_addresses=127.0.0.1\n"
            "Restart=on-failure\n\n"
            "[Install]\n"
            "WantedBy=default.target\n"
        )
        unit_dir = self._user_unit_dir()
        unit_dir.mkdir(parents=True, exist_ok=True)
        self.unit_path().write_text(content)
        run_command(self._systemctl("daemon-reload"), env=self._systemctl_env())

    def _user_unit_dir(self) -> Path:
        return Path.home() / ".config" / "systemd" / "user"

    def _provision_alpine(self) -> None:
        """apk neither initialises the data dir nor enables the service.
        Initialise once; safe to re-run."""
        if not self.is_provisioned():
            run_command(_privileged(["install", "-d", "-m", "700", "-o", "postgres", "-g", "postgres", str(self.data_dir())]))
            run_command(["sudo", "-u", "postgres", "initdb", "-D", str(self.data_dir())])
            run_command(service_enable_command(_ALPINE_SERVICE))
        if not self.is_running():
            self.start()

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
        # Unix-socket peer auth: on Alpine the bootstrap superuser is the
        # 'postgres' OS account; everywhere else it's whoever ran initdb (the
        # bench user itself, no sudo needed). -p targets this server's port.
        cmd = ["sudo", "-u", "postgres", "psql"] if is_alpine() else [self._psql() or "psql"]
        cmd += ["-p", str(self.config.port), "-v", "ON_ERROR_STOP=1", "-d", "postgres"]
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
