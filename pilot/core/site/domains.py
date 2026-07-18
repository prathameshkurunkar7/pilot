from __future__ import annotations

from typing import TYPE_CHECKING

from pilot.core.adapters.domain_provider import DomainRouteProvider

if TYPE_CHECKING:
    from pilot.core.site import Site


class SiteDomains:
    def __init__(self, site: "Site") -> None:
        self.site = site
        self._provider = DomainRouteProvider(site.bench)

    def generate_dns_records(self, domain: str) -> dict:
        return self._provider.generate_dns_records(self.site.config.name, domain)

    def register(self, domain: str) -> None:
        self._provider.register(self.site.config.name, domain)

    def deregister(self, domain: str) -> None:
        self._provider.deregister(self.site.config.name, domain)

    def names(self) -> list[str]:
        return self._provider.domains(self.site.config.name)

    def primary(self) -> str | None:
        return self._provider.primary(self.site.config.name)

    def set_primary(self, domain: str | None) -> None:
        self._provider.set_primary(self.site.config.name, domain)
