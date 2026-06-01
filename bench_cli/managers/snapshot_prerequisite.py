from __future__ import annotations

from abc import ABC, abstractmethod

from bench_cli.config.mariadb_config import MariaDBConfig


class SnapshotPrerequisite(ABC):
    @abstractmethod
    def __enter__(self) -> SnapshotPrerequisite: ...

    @abstractmethod
    def __exit__(self, *args: object) -> None: ...


class BenchSnapshotPrerequisite(SnapshotPrerequisite):
    def __enter__(self) -> BenchSnapshotPrerequisite:
        return self

    def __exit__(self, *args: object) -> None:
        pass


class MariaDBSnapshotPrerequisite(SnapshotPrerequisite):
    def __init__(self, config: MariaDBConfig) -> None:
        self._config = config
        self._connection = None

    def __enter__(self) -> MariaDBSnapshotPrerequisite:
        self._connection = self._connect()
        self._flush_and_lock()
        return self

    def __exit__(self, *args: object) -> None:
        if self._connection:
            self._unlock()
            self._connection.close()
            self._connection = None

    def _connect(self):
        import pymysql

        return pymysql.connect(
            host=self._config.host,
            port=self._config.port,
            user=self._config.admin_user,
            password=self._config.root_password,
            unix_socket=self._config.socket_path or None,
        )

    def _flush_and_lock(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("FLUSH TABLES WITH READ LOCK")

    def _unlock(self) -> None:
        with self._connection.cursor() as cursor:
            cursor.execute("UNLOCK TABLES")
