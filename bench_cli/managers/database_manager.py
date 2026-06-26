from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import AbstractContextManager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from bench_cli.config.bench_config import BenchConfig


class DatabaseManager(ABC):
    """Backend-neutral lifecycle contract used by bench commands."""

    engine: str

    @property
    @abstractmethod
    def is_dedicated(self) -> bool: ...

    @abstractmethod
    def is_installed(self) -> bool: ...

    @abstractmethod
    def install(self) -> None: ...

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def check_credentials(self, password: str | None = None) -> bool: ...

    @abstractmethod
    def provision_instance(self, staging_dir: Path) -> None: ...

    @abstractmethod
    def snapshot_lock(self) -> AbstractContextManager: ...


def create_database_manager(config: "BenchConfig") -> DatabaseManager:
    if config.database_engine == "postgres":
        from bench_cli.managers.postgres_manager import PostgresManager
        return PostgresManager(config.postgres)
    if config.database_engine == "sqlite":
        from bench_cli.managers.sqlite_manager import SQLiteManager
        return SQLiteManager(config.sqlite)
    from bench_cli.managers.mariadb_manager import MariaDBManager
    return MariaDBManager(config.mariadb)
