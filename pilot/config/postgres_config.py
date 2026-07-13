from dataclasses import dataclass


@dataclass
class PostgresConfig:
    # Connection to the single rootless, per-bench-user PostgreSQL server that
    # every bench on this host shares (see PostgresManager). root_password is
    # the superuser password new-site connects with.
    host: str = "localhost"
    port: int = 5432
    root_password: str = ""
    admin_user: str = "postgres"
