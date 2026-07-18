from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

from pilot.commands import Command


@dataclass(kw_only=True)
class UpdateConfigCommand(Command):
    name: ClassVar[str] = "config"
    help: ClassVar[str] = "Regenerate config files from bench.toml."
    group: ClassVar[str] = "setup"

    def run(self) -> None:
        from pilot.managers.nginx import NginxManager
        from pilot.managers.processes.local import ProcessManager
        from pilot.managers.redis import RedisManager

        self.report("Updating Redis configs...")
        RedisManager(self.bench.config.redis, self.bench).generate_configs()

        self.report("Updating process manager config...")
        ProcessManager.for_bench(self.bench).write_config()

        self.report("Updating common_site_config.json...")
        self.bench.write_common_site_config()

        if self.bench.config.production.enabled:
            self.report("Updating nginx configs...")
            NginxManager(self.bench).generate_config()
            self.report("  Note: run 'bench setup nginx' to reload nginx with the new config.")
