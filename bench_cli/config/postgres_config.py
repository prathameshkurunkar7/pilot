from dataclasses import dataclass
from typing import Optional


@dataclass
class PostgresConfig:
    """Connection and lifecycle settings for a PostgreSQL backend."""

    host: str = "localhost"
    port: int = 5432
    root_password: str = ""
    admin_user: str = "postgres"
    socket_path: str = ""
    version: Optional[str] = None
    instance: str = ""
    data_dir: str = ""
