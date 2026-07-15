from dataclasses import dataclass


@dataclass
class MariaDBConfig:
    # external is a deliberate user choice, never inferred from host (see MariaDBManager).
    host: str = "localhost"
    port: int = 3306
    root_password: str = ""
    admin_user: str = "root"
    socket_path: str = ""
    external: bool = False
