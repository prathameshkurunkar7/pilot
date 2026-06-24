from __future__ import annotations

import argparse
import shutil
import sys
from typing import TYPE_CHECKING

from bench_cli.commands.base import Command
from bench_cli.exceptions import BenchError

if TYPE_CHECKING:
    from bench_cli.core.bench import Bench


class DropBenchCommand(Command):
    name = "drop"
    help = "Delete a bench (must have no sites), tearing down its production services, nginx and MariaDB instance."
    # Deleting whichever bench happens to be active by default would be too easy
    # to trigger by accident, so require an explicit -b/--bench (or running from
    # inside the bench dir).
    requires_explicit_bench = True

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, skip_confirm=args.yes)

    def __init__(self, bench: "Bench", skip_confirm: bool = False) -> None:
        self.bench = bench
        self.skip_confirm = skip_confirm

    def run(self) -> None:
        name = self.bench.config.name
        self._validate_no_sites(name)
        self._confirm(name)

        self._remove_production()
        self._remove_mariadb_instance()
        self._delete_bench_dir()
        print(f"\nBench '{name}' dropped.")

    def _validate_no_sites(self, name: str) -> None:
        sites = self.bench.sites()
        if sites:
            listed = ", ".join(s.config.name for s in sites)
            raise BenchError(
                f"Bench '{name}' still has {len(sites)} site(s): {listed}. "
                f"Drop them first, then retry."
            )

    def _confirm(self, name: str) -> None:
        if self.skip_confirm:
            return
        answer = input(f"Permanently delete bench '{name}' and its MariaDB instance? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            raise BenchError("Aborted.")

    def _remove_production(self) -> None:
        if not self.bench.config.production.enabled:
            return
        from bench_cli.commands.remove.production import RemoveProductionCommand

        RemoveProductionCommand(self.bench).run()

    def _remove_mariadb_instance(self) -> None:
        from bench_cli.managers.mariadb_manager import MariaDBManager

        if self._mariadb_shared_with_other_bench():
            print("Keeping MariaDB instance — another bench shares it.")
            return
        print("Removing MariaDB instance...")
        sys.stdout.flush()
        try:
            MariaDBManager(self.bench.config.mariadb).remove_instance()
        except Exception as exc:  # never block the drop on a best-effort cleanup
            print(f"  (mariadb cleanup skipped: {exc})")

    def _mariadb_shared_with_other_bench(self) -> bool:
        """True if another bench connects to this bench's MariaDB — whether by
        dedicated instance name, datadir, unix socket, or host:port (a bench can
        be pointed at a sibling's database over any of these). Removing the
        instance would break that bench, so we leave its data in place."""
        from bench_cli.utils import iter_sibling_benches

        mine = self.bench.config.mariadb
        if not mine.instance:
            return False  # shared server: remove_instance is a no-op regardless

        mine_keys = self._mariadb_identity(mine)
        for _, cfg in iter_sibling_benches(self.bench.path):
            other = getattr(cfg, "mariadb", None)
            if other and (mine_keys & self._mariadb_identity(other)):
                return True
        return False

    @staticmethod
    def _mariadb_identity(cfg) -> set:
        """The set of connection identities a MariaDB config resolves to. Two
        benches share a database iff their identity sets intersect."""
        from bench_cli.managers.mariadb_manager import MariaDBManager

        host = "127.0.0.1" if cfg.host in ("localhost", "127.0.0.1", "") else cfg.host
        keys = {("tcp", host, cfg.port)}
        if cfg.instance:
            mgr = MariaDBManager(cfg)
            keys |= {
                ("instance", cfg.instance),
                ("datadir", mgr.data_dir()),
                ("socket", mgr.instance_socket()),
            }
        if cfg.socket_path:
            keys.add(("socket", cfg.socket_path))
        if cfg.data_dir:
            keys.add(("datadir", cfg.data_dir))
        return keys

    def _delete_bench_dir(self) -> None:
        path = self.bench.path
        print(f"Deleting {path}...")
        sys.stdout.flush()
        shutil.rmtree(path, ignore_errors=True)
