import shutil
from contextlib import contextmanager
from pathlib import Path

from bench_cli.config.mariadb_config import MariaDBConfig
from bench_cli.platform import (
    _privileged,
    get_package_manager,
    is_alpine,
    is_macos,
    service_command,
    service_enable_command,
)
from bench_cli.utils import run_command

_MACOS_SOCKET_CANDIDATES = ["/tmp/mysql.sock", "/usr/local/var/mysql/mysql.sock"]
_LINUX_SOCKET_CANDIDATES = ["/var/run/mysqld/mysqld.sock", "/run/mysqld/mysqld.sock"]
_ALPINE_DATA_DIR = Path("/var/lib/mysql")


class MariaDBManager:
    def __init__(self, config: MariaDBConfig) -> None:
        self.config = config

    def is_installed(self) -> bool:
        return bool(shutil.which("mysqld") or shutil.which("mariadbd"))

    def install(self) -> None:
        if not self.is_installed():
            get_package_manager().install(*self._packages())
        if is_alpine():
            # Idempotent: Alpine's mariadb package ships an empty data dir and does
            # not enable the service — initialise and enable on every init.
            self._initialize_data_dir()
            run_command(service_enable_command("mariadb"))

    def _packages(self) -> list[str]:
        if is_macos():
            return [self._brew_package()]
        if is_alpine():
            return ["mariadb", "mariadb-client"]
        return [self._apt_package()]

    def _initialize_data_dir(self) -> None:
        if (_ALPINE_DATA_DIR / "mysql").is_dir():
            return
        run_command(_privileged([
            "mariadb-install-db",
            "--user=mysql",
            f"--datadir={_ALPINE_DATA_DIR}",
            "--skip-test-db",
        ]))

    def start(self) -> None:
        if is_macos():
            run_command(["brew", "services", "start", self._brew_package()])
        else:
            run_command(service_command("start", "mariadb"))

    def stop(self) -> None:
        if is_macos():
            run_command(["brew", "services", "stop", self._brew_package()])
        else:
            run_command(service_command("stop", "mariadb"))

    def _brew_package(self) -> str:
        if self.config.version:
            return f"mariadb@{self.config.version}"
        return "mariadb"

    def _apt_package(self) -> str:
        if self.config.version:
            return f"mariadb-server-{self.config.version}"
        return "mariadb-server"

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

    def _connect(self):
        import pymysql

        return pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.admin_user,
            password=self.config.root_password,
            unix_socket=self._detect_socket() or None,
        )

    def _detect_socket(self) -> str:
        if self.config.socket_path:
            return self.config.socket_path
        candidates = _MACOS_SOCKET_CANDIDATES if is_macos() else _LINUX_SOCKET_CANDIDATES
        for path in candidates:
            if Path(path).exists():
                return path
        return ""
