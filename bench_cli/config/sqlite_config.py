from dataclasses import dataclass


@dataclass
class SQLiteConfig:
    """SQLite has no server credentials; Frappe stores each DB inside its site."""

    timeout_seconds: int = 15
