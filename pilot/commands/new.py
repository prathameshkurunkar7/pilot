import argparse
import secrets
import socket
from pathlib import Path

from pilot.commands.base import Command
from pilot.exceptions import BenchAlreadyExistsError
from pilot.utils import iter_sibling_benches


class NewCommand(Command):
    name = "new"
    help = "Create a new bench."
    requires_bench = False

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("name", help="Name for the new bench.")
        parser.add_argument(
            "--admin-domain",
            default="",
            help="Admin domain for this bench. Optional for development; "
            "required by 'bench setup production' (pass it there if omitted here).",
        )
        parser.add_argument(
            "--database",
            default="mariadb",
            choices=["mariadb", "postgres", "sqlite"],
            help="Database engine for this bench's sites (default: mariadb).",
        )

    @classmethod
    def from_args(cls, args, bench):
        from pilot.loader import cli_root

        return cls(
            cli_root() / "benches" / args.name,
            args.name,
            admin_domain=args.admin_domain,
            db_type=args.database,
        )

    def __init__(
        self,
        target_directory: Path,
        name: str,
        process_manager: str = "",
        admin_domain: str = "",
        admin_tls: bool | None = None,
        db_type: str = "mariadb",
    ) -> None:
        self.target_directory = target_directory
        self.name = name
        self.process_manager = process_manager
        self.admin_domain = admin_domain
        # None → inherit the server-wide value from a sibling bench (default False).
        self.admin_tls = admin_tls
        self.db_type = db_type

    def run(self) -> None:
        from pilot.config.bench_toml_builder import default_ports
        from pilot.config.host_toml_store import HostTomlStore
        from pilot.config.toml_store import BenchTomlStore

        bench_toml = self.target_directory / "bench.toml"
        if bench_toml.exists():
            raise BenchAlreadyExistsError(f"Bench '{self.name}' already exists.")

        benches_dir = self.target_directory.parent
        if not benches_dir.exists():
            print(f"Creating benches directory at {benches_dir}")
            benches_dir.mkdir(parents=True, exist_ok=True)

        print(f"Creating bench directory: {self.target_directory}")
        self.target_directory.mkdir(parents=True, exist_ok=True)

        offset = self._pick_port_offset(self.target_directory)
        print("Writing bench.toml")

        with HostTomlStore.for_bench(self.target_directory).edit() as host:
            self._backfill_host_config(host)

            admin_tls = self.admin_tls if self.admin_tls is not None else host.admin_tls
            host.admin_tls = admin_tls
            # admin.domain is left empty unless given: development serves the admin on
            # localhost, and 'bench setup production' requires a real domain (via its
            # --admin-domain flag or here), erroring rather than deploying a placeholder.
            settings = {
                "admin_enabled": True,
                "admin_domain": self.admin_domain,
                "admin_tls": admin_tls,
                "db_type": self.db_type,
            }
            if self.db_type == "mariadb":
                host.mariadb_port = host.mariadb_port or self._pick_mariadb_port()
                host.mariadb_root_password = host.mariadb_root_password or secrets.token_hex(nbytes=8)
                settings["mariadb_port"] = host.mariadb_port
                settings["mariadb_password"] = host.mariadb_root_password
            if self.db_type == "postgres":
                host.postgres_port = host.postgres_port or self._pick_postgres_port()
                host.postgres_root_password = host.postgres_root_password or secrets.token_hex(nbytes=8)
                settings["postgres_port"] = host.postgres_port
                settings["postgres_password"] = host.postgres_root_password
            if self.process_manager:
                settings["production_process_manager"] = self.process_manager

            if host.letsencrypt_email:
                settings["letsencrypt_email"] = host.letsencrypt_email

            if host.admin_jwks_url:
                settings["admin_jwks_url"] = host.admin_jwks_url
                if host.admin_jwks_audience:
                    settings["admin_jwks_audience"] = host.admin_jwks_audience

        BenchTomlStore(bench_toml).write_flat(self.name, settings, port_offset=offset)

        admin_port = default_ports()["admin.port"] + offset
        print(f"\nBench '{self.name}' created at {self.target_directory}")
        print("\nNext step:")
        print("  bench start")
        print(f"  Then open http://localhost:{admin_port} — the setup wizard takes it from there.")

    def _backfill_host_config(self, host) -> None:
        """One-time bootstrap for a host upgrading from before host.toml existed:
        fill any still-empty field from whatever a sibling bench.toml already
        established, so the shared MariaDB/Postgres server, ACME account, and
        admin JWKS trust survive unchanged. Once populated, later bench creations
        read straight from host.toml and never scan siblings for this."""
        host.mariadb_port = host.mariadb_port or self._sibling_mariadb_port()
        host.mariadb_root_password = host.mariadb_root_password or self._sibling_mariadb_password()
        host.postgres_port = host.postgres_port or self._sibling_postgres_port()
        host.postgres_root_password = host.postgres_root_password or self._sibling_postgres_password()
        host.letsencrypt_email = host.letsencrypt_email or self._sibling_letsencrypt_email()
        if not host.admin_jwks_url:
            sibling_admin = self._sibling_jwks_admin()
            if sibling_admin:
                host.admin_jwks_url = sibling_admin.jwks_url
                host.admin_jwks_audience = sibling_admin.jwks_audience or ""
        host.admin_tls = host.admin_tls or self._sibling_admin_tls()

    def _sibling_letsencrypt_email(self) -> str:
        """The Let's Encrypt email from any sibling bench that has one, so a new
        production bench inherits the server-wide ACME account."""
        for _, config in iter_sibling_benches(self.target_directory):
            email = getattr(config.letsencrypt, "email", "")
            if email:
                return email
        return ""

    def _sibling_mariadb_port(self) -> int:
        """The MariaDB port a sibling bench already established for the
        shared user-owned server (see MariaDBManager), so this bench points
        at the same running instance instead of a fresh guess."""
        for _, config in iter_sibling_benches(self.target_directory):
            if config.db_type == "mariadb" and config.mariadb.port:
                return config.mariadb.port
        return 0

    def _pick_mariadb_port(self) -> int:
        """Smallest port at/above the default 3306 that isn't already live —
        used only when no sibling has picked one yet, so the very first
        MariaDB bench on a host doesn't collide with a system-wide MariaDB
        already listening on 3306.

        macOS never creates a bindable-anywhere instance of its own —
        MariaDBManager just starts Homebrew's single shared service via
        `brew services`.
        """
        from pilot.config.mariadb_config import MariaDBConfig
        from pilot.platform import is_macos

        port = MariaDBConfig().port
        if is_macos():
            return port
        while self._port_is_live(port):
            port += 1
        return port

    def _sibling_mariadb_password(self) -> str:
        """The MariaDB root password from any sibling MariaDB bench — every
        bench for this OS user shares one server (see MariaDBManager)."""
        for _, config in iter_sibling_benches(self.target_directory):
            if config.db_type == "mariadb" and config.mariadb.root_password:
                return config.mariadb.root_password
        return ""

    def _sibling_postgres_port(self) -> int:
        """The PostgreSQL port a sibling bench already established for the
        shared server (see PostgresManager), so this bench points at the
        same running instance instead of a fresh guess."""
        for _, config in iter_sibling_benches(self.target_directory):
            if config.db_type == "postgres" and config.postgres.port:
                return config.postgres.port
        return 0

    def _pick_postgres_port(self) -> int:
        """Smallest port at/above the default 5432 that isn't already live —
        used only when no sibling has picked one yet, so the very first
        Postgres bench on a host doesn't collide with a system-wide
        PostgreSQL already listening on 5432. Mirrors _pick_mariadb_port().

        macOS never creates a bindable-anywhere instance of its own —
        PostgresManager just starts Homebrew's single shared service via
        `brew services`
        """
        from pilot.config.postgres_config import PostgresConfig
        from pilot.platform import is_macos

        port = PostgresConfig().port
        if is_macos():
            return port
        while self._port_is_live(port):
            port += 1
        return port

    def _sibling_postgres_password(self) -> str:
        """The PostgreSQL superuser password from any sibling Postgres bench —
        every bench for this OS user shares one server (see PostgresManager)."""
        for _, config in iter_sibling_benches(self.target_directory):
            if config.db_type == "postgres" and config.postgres.root_password:
                return config.postgres.root_password
        return ""

    def _sibling_jwks_admin(self):
        """The admin config of the first sibling that trusts a remote JWKS
        issuer, so a new bench inherits the same jwks_url and audience."""
        for _, config in iter_sibling_benches(self.target_directory):
            if getattr(config.admin, "jwks_url", ""):
                return config.admin
        return None

    def _sibling_admin_tls(self) -> bool:
        """Carry forward the server-wide TLS choice from a sibling bench; default
        to False (plain HTTP, enable TLS explicitly) when this is the first bench."""
        for _, config in iter_sibling_benches(self.target_directory):
            return bool(getattr(config.admin, "tls", False))
        return False

    def _pick_port_offset(self, bench_path: Path) -> int:
        """Smallest offset (added to every base port) that collides with
        neither another bench's bench.toml nor a port that's actually live
        right now — covers both stale configs and orphaned processes."""
        from pilot.config.bench_toml_builder import default_ports

        bases = default_ports()
        base_http_port = bases["http_port"]
        used = set()

        for _, config in iter_sibling_benches(bench_path):
            try:
                used.add(config.http_port - base_http_port)
            except Exception:
                continue

        admin_internal_port = bases["admin.port"] + 1

        offset = 0
        while (
            offset in used
            or any(self._port_is_live(base + offset) for base in bases.values())
            or self._port_is_live(admin_internal_port + offset)
        ):
            offset += 1
        return offset

    @staticmethod
    def _port_is_live(port: int) -> bool:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return True
        except OSError:
            return False
