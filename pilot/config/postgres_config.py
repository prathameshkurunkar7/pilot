from dataclasses import dataclass


@dataclass
class PostgresConfig:
    # external is a deliberate user choice, never inferred from host (see PostgresManager).
    host: str = "localhost"
    port: int = 5432
    root_password: str = ""
    admin_user: str = "postgres"
    external: bool = False
