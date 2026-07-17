import argparse
from pathlib import Path

from pilot.commands.base import Command


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
        self.name = name  # type: ignore[misc]  # the new bench's name, distinct from Command.name (the CLI verb "new")
        self.process_manager = process_manager
        self.admin_domain = admin_domain
        # None → inherit the server-wide value from a sibling bench (default False).
        self.admin_tls = admin_tls
        self.db_type = db_type

    def run(self) -> None:
        from pilot.core.bench import Bench

        Bench.create_at(
            self.target_directory,
            self.name,
            process_manager=self.process_manager,
            admin_domain=self.admin_domain,
            admin_tls=self.admin_tls,
            db_type=self.db_type,
            on_progress=self.print,
        )
