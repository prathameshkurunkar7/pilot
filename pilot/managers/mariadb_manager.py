import os
import socket
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path

from pilot.config.mariadb_config import MariaDBConfig
from pilot.package_managers import get_package_manager
from pilot.platform import is_macos, which
from pilot.utils import run_command

DEFAULT_VERSION = "11.8"

# One MariaDB server per bench user, shared by every bench they own — rootless,
# running as a single systemd --user unit. Fixed locations, no per-bench units.
_STATE_DIR = Path.home() / ".local" / "share" / "pilot" / "mariadb"
_UNIT_NAME = "pilot-mariadb.service"


class MariaDBManager:
    def __init__(self, config: MariaDBConfig) -> None:
        self.config = config

    def data_dir(self) -> Path:
        return _STATE_DIR / "data"

    def pid_file(self) -> Path:
        return _STATE_DIR / "mysqld.pid"

    def socket_path(self) -> str:
        if self.config.socket_path:
            return self.config.socket_path
        return str(_STATE_DIR / "mysqld.sock")

    def is_installed(self) -> bool:
        # which() searches sbin too; mysqld/mariadbd live in /usr/sbin.
        return bool(which("mysqld") or which("mariadbd"))

    def install(self) -> None:
        if self.is_installed():
            return
        if is_macos():
            get_package_manager().install(self._brew_package())
            return
        raise RuntimeError(
            "MariaDB is not installed. Re-run install.sh as root to install it "
            "(it provisions mariadb-server for every supported distro), or "
            "install 'mariadb-server' yourself."
        )

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
        result = subprocess.run(
            self._systemctl("is-active", _UNIT_NAME), env=self._systemctl_env(), capture_output=True
        )
        return result.returncode == 0

    def start(self) -> None:
        if is_macos():
            run_command(["brew", "services", "start", self._brew_package()])
        else:
            run_command(self._systemctl("start", _UNIT_NAME), env=self._systemctl_env())

    def restart(self) -> None:
        if is_macos():
            run_command(["brew", "services", "restart", self._brew_package()])
        else:
            run_command(self._systemctl("restart", _UNIT_NAME), env=self._systemctl_env())

    def stop(self) -> None:
        if is_macos():
            run_command(["brew", "services", "stop", self._brew_package()])
        else:
            run_command(self._systemctl("stop", _UNIT_NAME), env=self._systemctl_env())

    def _provision_macos(self):
        if not self.is_running():
            self.start()
        self._wait_until_reachable()
        self.secure_installation()

    def provision(self) -> None:
        """Ensure the shared MariaDB server is installed, running and secured.
        Idempotent and safe for every bench to call — the first bench for this
        user provisions it, later benches just reuse the already-running server.
        """
        self.install()
        if is_macos():
            return self._provision_macos()

        if not self.is_provisioned():
            self._initialize_data_dir()
            self._install_unit()
            run_command(self._systemctl("enable", "--now", _UNIT_NAME), env=self._systemctl_env())

        elif not self.is_running():
            run_command(self._systemctl("start", _UNIT_NAME), env=self._systemctl_env())

        self._wait_until_reachable()
        self.secure_installation()

    def _initialize_data_dir(self) -> None:
        self.data_dir().mkdir(parents=True, exist_ok=True)
        run_command(["mariadb-install-db", f"--datadir={self.data_dir()}", "--skip-test-db"])

    def _install_unit(self) -> None:
        mariadbd = which("mariadbd") or which("mysqld") or "/usr/sbin/mariadbd"
        content = (
            "[Unit]\n"
            "Description=MariaDB (pilot, user-owned)\n\n"
            "[Service]\n"
            "Type=simple\n"
            f"ExecStart={mariadbd} --datadir={self.data_dir()} --socket={self.socket_path()} "
            f"--port={self.config.port} --pid-file={self.pid_file()} --bind-address=127.0.0.1\n"
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

    def _version(self) -> str:
        return DEFAULT_VERSION

    def _brew_package(self) -> str:
        return self._installed_brew_formula() or f"mariadb@{self._version()}"

    def _installed_brew_formula(self) -> str | None:
        """Return the mariadb formula Homebrew already manages (e.g. 'mariadb@10.6').

        When bench.toml doesn't pin a version, start/stop must target whatever
        brew actually installed — assuming plain 'mariadb' fails when only a
        versioned formula like mariadb@10.6 is present.
        """
        result = subprocess.run(["brew", "list", "--formula"], capture_output=True, text=True)
        if result.returncode != 0:
            return None
        formulae = result.stdout.split()
        if "mariadb" in formulae:
            return "mariadb"
        return next((f for f in formulae if f.startswith("mariadb@")), None)

    def _brew_service_running(self) -> bool:
        result = subprocess.run(["brew", "services", "list"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            parts = line.split()
            if parts and parts[0] == self._brew_package() and "started" in parts:
                return True
        return False

    def _wait_until_reachable(self, timeout: float = 30.0) -> None:
        """Poll until the server is active and its socket exists, so securing
        doesn't race the daemon's startup. Falls through on timeout — the next
        step surfaces a clear connection error."""
        socket_path = self.socket_path()
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.is_running() and Path(socket_path).exists():
                return
            time.sleep(0.5)

    def is_unsecured(self) -> bool:
        """True if the admin account has no password and is reachable via
        unix-socket auth (i.e. a fresh, not-yet-secured install). The bench
        user owns this server outright, so no privilege escalation is needed
        to connect as its admin account."""
        cmd = [
            "mariadb",
            f"--socket={self.socket_path()}",
            "-u",
            self.config.admin_user,
            "--batch",
            "--skip-column-names",
            "-e",
            "SELECT 1",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.returncode == 0

    def check_credentials(self, password: str | None = None) -> bool:
        """True if the admin user can connect with the given password (default:
        configured root password). Uses the ``mariadb`` client, not pymysql, so
        the zero-dep CLI works during init; password goes via MYSQL_PWD, not argv."""
        pw = self.config.root_password if password is None else password
        cmd = ["mariadb", "-u", self.config.admin_user, "--batch", "--skip-column-names"]
        socket_path = self._detect_socket()
        if socket_path:
            cmd.append(f"--socket={socket_path}")
        else:
            cmd += ["-h", self.config.host, "-P", str(self.config.port)]
        cmd += ["-e", "SELECT 1"]
        result = subprocess.run(
            cmd, env={**os.environ, "MYSQL_PWD": pw}, capture_output=True, text=True
        )
        return result.returncode == 0

    def secure_installation(self) -> None:
        """Ensure the configured admin account exists with the configured
        password, and apply some hardening. Idempotent — a no-op once
        check_credentials() already succeeds."""
        if self.check_credentials():
            return
        user = self.config.admin_user
        password = self._sql_quote(self.config.root_password)
        statements = [
            # CREATE...IF NOT EXISTS + ALTER covers both a fresh install (no
            # such account yet) and a server another bench already secured
            # with a different password.
            f"CREATE USER IF NOT EXISTS '{user}'@'localhost' IDENTIFIED BY {password};",
            f"ALTER USER '{user}'@'localhost' IDENTIFIED BY {password};",
            f"GRANT ALL PRIVILEGES ON *.* TO '{user}'@'localhost' WITH GRANT OPTION;",
            "DROP USER IF EXISTS ''@'localhost';",
            "DROP USER IF EXISTS ''@'%';",
            "DROP DATABASE IF EXISTS test;",
            "FLUSH PRIVILEGES;",
        ]
        self._run_sql_as_superuser("\n".join(statements))

    def _run_sql_as_superuser(self, sql: str) -> None:
        # No explicit -u: this runs as the bench user directly —
        # mariadb-install-db (run earlier, also as the bench user) already
        # granted that exact OS username full unix_socket-authenticated
        # access, so no privilege escalation or pre-existing account is
        # required to bootstrap from here.
        cmd = ["mariadb", f"--socket={self.socket_path()}"]
        subprocess.run(cmd, input=sql, text=True, check=True)

    @staticmethod
    def _sql_quote(value: str) -> str:
        """Quote a value as a MariaDB string literal (escaping \\ and ')."""
        escaped = value.replace("\\", "\\\\").replace("'", "\\'")
        return f"'{escaped}'"

    def kill_process(self, process_id: int) -> None:
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("KILL %s", (process_id,))
        finally:
            connection.close()

    @contextmanager
    def snapshot_lock(self):
        connection = self._connect()
        try:
            with connection.cursor() as cursor:
                cursor.execute("FLUSH TABLES WITH READ LOCK")
            yield
        finally:
            with connection.cursor() as cursor:
                cursor.execute("UNLOCK TABLES")
            connection.close()

    def _connect(self, password: str | None = None):
        import pymysql

        return pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.admin_user,
            password=self.config.root_password if password is None else password,
            unix_socket=self._detect_socket() or None,
        )

    def _detect_socket(self) -> str:
        if self.config.socket_path:
            return self.config.socket_path
        if not is_macos() and Path(self.socket_path()).exists():
            return self.socket_path()
        return ""
