from __future__ import annotations

import json
from typing import TYPE_CHECKING

from bench_cli.exceptions import BenchError
from bench_cli.utils import host_owner, normalize_host

if TYPE_CHECKING:
    from bench_cli.core.bench import Bench


class DomainController:
    """Manage the custom domains pointed at a single site: ownership verification,
    persistence in site_config.json, and the primary (canonical) domain.

    nginx serves a site under every name in its site_config ``domains`` list (see
    Bench.sites); Frappe redirects to ``host_name`` when set, giving us the
    primary-domain behaviour for free. This class is the one place that edits
    those keys — callers re-run nginx/letsencrypt afterwards to apply routing.
    """

    def __init__(self, bench: "Bench", site_name: str) -> None:
        self.bench = bench
        self.site_name = site_name

    @property
    def _config_path(self):
        return self.bench.sites_path / self.site_name / "site_config.json"

    def _read(self) -> dict:
        if not self._config_path.exists():
            raise BenchError(f"Site '{self.site_name}' not found.")
        return json.loads(self._config_path.read_text())

    def _write(self, config: dict) -> None:
        self._config_path.write_text(json.dumps(config, indent=1))

    @staticmethod
    def _names(config: dict) -> list[str]:
        out = []
        for entry in config.get("domains") or []:
            name = entry.get("domain") if isinstance(entry, dict) else entry
            if isinstance(name, str) and name:
                out.append(name)
        return out

    def domains(self) -> list[str]:
        return self._names(self._read())

    def primary(self) -> str | None:
        host = (self._read().get("host_name") or "").strip()
        return host.split("://", 1)[-1] or None if host else None

    def _validate_new(self, domain: str) -> str:
        """Normalize ``domain`` and raise if it can't be attached to this site
        (already attached here, or owned by another bench). Shared by the two
        steps of attaching a domain: showing DNS records, then verify+add."""
        domain = normalize_host(domain)
        if not domain:
            raise BenchError("A domain is required.")
        if domain == normalize_host(self.site_name) or domain in (normalize_host(d) for d in self.domains()):
            raise BenchError(f"{domain} is already attached to this site.")
        owner = host_owner(self.bench.path, domain)
        if owner:
            raise BenchError(f"{domain} is already used by bench '{owner}'. Hostnames must be unique across benches.")
        return domain

    def get_dns_records(self, domain: str) -> dict:
        """Step 1 of attaching a domain: validate it's free, then return the DNS
        record options the user can pick from to point it at this server."""
        domain = self._validate_new(domain)
        return {
            "cname": {"type": "CNAME", "host": domain, "value": self.site_name},
            "a": {"type": "A", "host": domain, "value": self.server_ip()},
        }

    @staticmethod
    def server_ip() -> str:
        """Best-effort public IP of this server, for the A-record option.
        Tries the outbound-route trick first (no packets actually sent to
        8.8.8.8); falls back to an external echo service since the route trick
        only yields a private IP behind NAT/PaaS (e.g. SwiftWave)."""
        import socket

        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                ip = s.getsockname()[0]
            if not ip.startswith(("10.", "172.", "192.168.", "127.")):
                return ip
        except OSError:
            pass

        import urllib.request

        try:
            with urllib.request.urlopen("https://ifconfig.me/ip", timeout=3) as resp:
                return resp.read().decode().strip()
        except OSError:
            return ""

    def verify(self, domain: str) -> None:
        """Raise BenchError unless ``domain`` resolves to the same server as this
        site — i.e. its DNS points here. Needs no nginx/sudo: a CNAME to the site
        name (or an A record to this server) resolves to the same address set."""
        candidate = self._resolve(domain)
        if not candidate:
            raise BenchError(
                f"{domain} does not resolve yet. Add a CNAME from {domain} to {self.site_name}, "
                f"then retry — new DNS records can take a few minutes to propagate."
            )
        if not (candidate & self._resolve(self.site_name)):
            raise BenchError(
                f"{domain} does not point to this server yet. Point it here "
                f"(CNAME to {self.site_name}), then retry once DNS has propagated."
            )

    @staticmethod
    def _resolve(host: str) -> set[str]:
        import socket

        try:
            return {info[4][0] for info in socket.getaddrinfo(host, None)}
        except OSError:
            return set()

    def add(self, domain: str) -> None:
        """Step 2: re-validate, verify DNS, then persist."""
        domain = self._validate_new(domain)
        self.verify(domain)

        config = self._read()
        config.setdefault("domains", [])
        config["domains"].append(domain)
        self._write(config)

    def remove(self, domain: str) -> None:
        domain = normalize_host(domain)
        primary = self.primary()
        if primary and normalize_host(primary) == domain:
            raise BenchError("Cannot remove the primary domain. Make another domain primary first.")
        config = self._read()
        config["domains"] = [d for d in (config.get("domains") or []) if normalize_host(self._name(d)) != domain]
        self._write(config)

    def set_primary(self, domain: str | None) -> None:
        config = self._read()
        if not domain:
            config.pop("host_name", None)
            self._write(config)
            return
        domain = normalize_host(domain)
        candidates = {normalize_host(self.site_name)} | {normalize_host(d) for d in self.domains()}
        if domain not in candidates:
            raise BenchError(f"{domain} is not a domain of this site.")
        scheme = "https" if config.get("ssl") else "http"
        config["host_name"] = f"{scheme}://{domain}"
        self._write(config)

    @staticmethod
    def _name(entry) -> str:
        return entry.get("domain", "") if isinstance(entry, dict) else str(entry)
