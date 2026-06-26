from dataclasses import dataclass
from typing import Optional


@dataclass
class PostgresConfig:
    # Connection to the PostgreSQL server bench installs and provisions during
    # init. root_password is the superuser password new-site connects with.
    host: str = "localhost"
    port: int = 5432
    root_password: str = ""
    admin_user: str = "postgres"
    version: Optional[str] = None
