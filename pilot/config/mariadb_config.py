from dataclasses import dataclass


@dataclass
class MariaDBConfig:
    # Connection to the single rootless, per-bench-user MariaDB server that
    # every bench on this host shares (see MariaDBManager).
    host: str = "localhost"
    port: int = 3306
    root_password: str = ""
    admin_user: str = "root"
    socket_path: str = ""
