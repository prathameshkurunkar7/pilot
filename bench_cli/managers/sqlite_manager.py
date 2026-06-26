from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

from bench_cli.config.sqlite_config import SQLiteConfig


class SQLiteManager:
    """Serverless database backend used by Frappe's experimental SQLite mode."""

    engine = "sqlite"

    def __init__(self, config: SQLiteConfig) -> None:
        self.config = config

    @property
    def is_dedicated(self) -> bool:
        return False

    def is_installed(self) -> bool:
        import sqlite3
        return bool(sqlite3.sqlite_version)

    def install(self) -> None:
        return None

    def start(self) -> None:
        return None

    def stop(self) -> None:
        return None

    def check_credentials(self, password: str | None = None) -> bool:
        return self.is_installed()

    def provision_instance(self, staging_dir: Path) -> None:
        return None

    @contextmanager
    def snapshot_lock(self):
        # SQLite files reside under sites/, which is already part of the bench
        # dataset. Frappe enables WAL mode and handles database consistency.
        yield

    def kill_process(self, process_id: int) -> None:
        raise RuntimeError("SQLite has no server processes to terminate")
