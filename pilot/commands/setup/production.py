from __future__ import annotations

import argparse
from typing import TYPE_CHECKING, Optional

from pilot.commands.base import Command

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class SetupProductionCommand(Command):
    name = "production"
    help = "Deploy a bench to production (process manager + nginx)."
    group = "setup"

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--process-manager",
            choices=["systemd", "supervisord"],
            default=None,
            help="Process manager to deploy with (defaults to production.process_manager in bench.toml, or systemd).",
        )
        parser.add_argument(
            "--admin-domain",
            default=None,
            help="Admin domain the deployment is reached at (required: pass it here or set admin.domain in bench.toml).",
        )
        parser.add_argument(
            "--tls",
            dest="admin_tls",
            action="store_true",
            default=None,  # None = leave the bench.toml value untouched; only --tls turns it on
            help="Terminate TLS via Let's Encrypt for the admin and SSL-enabled sites. "
            "Omit to serve plain HTTP (a central proxy may terminate TLS upstream).",
        )
        parser.add_argument(
            "--letsencrypt-email",
            dest="letsencrypt_email",
            default=None,
            help="Contact email for Let's Encrypt (required with --tls unless letsencrypt.email is already set in bench.toml).",
        )

    @classmethod
    def from_args(cls, args, bench):
        return cls(
            bench,
            process_manager=args.process_manager,
            admin_domain=args.admin_domain,
            admin_tls=args.admin_tls,
            letsencrypt_email=args.letsencrypt_email,
        )

    def __init__(
        self,
        bench: "Bench",
        process_manager: Optional[str] = None,
        admin_domain: Optional[str] = None,
        admin_tls: Optional[bool] = None,
        letsencrypt_email: Optional[str] = None,
        best_effort_tls: bool = False,
    ) -> None:
        self.bench = bench
        self.process_manager = process_manager
        self.admin_domain = admin_domain
        self.admin_tls = admin_tls
        self.letsencrypt_email = letsencrypt_email
        self.best_effort_tls = best_effort_tls

    def run(self) -> None:
        self.bench.setup_production(
            process_manager=self.process_manager,
            admin_domain=self.admin_domain,
            admin_tls=self.admin_tls,
            letsencrypt_email=self.letsencrypt_email,
            best_effort_tls=self.best_effort_tls,
            on_progress=self.print,
        )
