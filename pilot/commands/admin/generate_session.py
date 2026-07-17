from __future__ import annotations

import argparse
import urllib.parse
from typing import TYPE_CHECKING

from pilot.commands.base import Command
from pilot.exceptions import BenchError

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class GenerateSessionCommand(Command):
    name = "generate-admin-session"
    help = "Issue a 5-minute one-time sign-in token (use --full-path for a sign-in URL)."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        parser.add_argument("--full-path", action="store_true",
                            help="Print the full admin URL with ?sid= instead of the bare token.")

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, full_path=args.full_path)

    def __init__(self, bench: "Bench", full_path: bool = False) -> None:
        self.bench = bench
        self.full_path = full_path

    def run(self) -> None:
        from pilot.admin_url import admin_url
        from pilot.core.admin_auth import issue_login_token

        if not self.bench.config.admin.password:
            raise BenchError("Admin has no password set; configure [admin].password in bench.toml first.")
        token = issue_login_token(self._jwt_secret())
        if self.full_path:
            self.print(f"{admin_url(self.bench.config)}/?sid={urllib.parse.quote(token, safe='')}")
        else:
            self.print(token)

    def _jwt_secret(self) -> str:
        from pilot.core.admin_auth import ensure_jwt_secret

        secret = ensure_jwt_secret(self.bench.path / "bench.toml")
        self.bench.config.admin.jwt_secret = secret
        return secret


class IssueSiteTokenCommand(Command):
    name = "issue-site-token"
    help = "Issue a scoped JWT for site-to-bench API calls."

    @classmethod
    def add_arguments(cls, parser: argparse.ArgumentParser) -> None:
        from pilot.core.admin_auth import DEFAULT_TTL

        parser.add_argument("site", help="Site name to scope the token to.")
        parser.add_argument("--ttl", type=int, default=DEFAULT_TTL,
                            help="Token TTL in seconds (default: 86400).")

    @classmethod
    def from_args(cls, args, bench):
        return cls(bench, args.site, ttl=args.ttl)

    def __init__(self, bench: "Bench", site: str, ttl: int | None = None) -> None:
        from pilot.core.admin_auth import DEFAULT_TTL

        self.bench = bench
        self.site = site
        self.ttl = ttl if ttl is not None else DEFAULT_TTL

    def run(self) -> None:
        from pilot.core.admin_auth import ensure_jwt_secret, issue_site_token

        secret = ensure_jwt_secret(self.bench.path / "bench.toml")
        self.bench.config.admin.jwt_secret = secret
        self.print(issue_site_token(secret, self.site, ttl=self.ttl))
