"""This module houses the light-weight monitoring daemon that will do the following
- Collect CPU usage.
- Memory Consumption.
- DB bottleneck.

- Dump them into a monitor.json file path defined it `bench.toml`
- Logrotate the monitor.json file
"""

import getpass
import os
import pstats
import subprocess
from pathlib import Path

import psutil

from pilot.loader import cli_root
from pilot.managers.admin_env_manager import AdminEnvManager
from pilot.utils import run_command

# A plain long-running `systemd --user` daemon: no socket activation (it samples
# continuously) and no idle timeout. It runs from the cli root so both `pilot`
# and `admin` import, using the admin venv's Python (which has psutil/pymysql).
MONITOR_DAEMON_TEMPLATE = """\
[Unit]
Description={bench_name} monitor

[Service]
Type=simple
WorkingDirectory={cli_root}
Environment=PYTHONPATH={cli_root}
Environment=BENCH_MONITOR_ROOT={bench_root}
ExecStart={python} -m pilot.core.monitor {bench_root}
Restart=on-failure
RestartSec=5
StandardOutput=append:{bench_logs}/monitor.log
StandardError=append:{bench_logs}/monitor.log.error.log

[Install]
WantedBy=default.target
"""


class ConfigureMonitor:
    """Generates and installs a `systemd --user` unit for the monitor daemon.

    Mirrors SystemdProcessManager: the unit file lives under the bench's
    config/ dir and is symlinked into ~/.config/systemd/user/. The unit name is
    namespaced by bench so multiple benches don't clash on a shared `monitor.service`.
    """

    def __init__(self, bench_root: Path):
        from pilot.core.bench import Bench, BenchConfig

        self.bench = Bench(BenchConfig.from_file(bench_root / "bench.toml"), bench_root)
        self.unit_name = f"{self.bench.config.name}-monitor.service"
        self.monitor_service_path = self.bench.config_path / "monitor" / self.unit_name
        self.user_unit_dir = Path.home() / ".config" / "systemd" / "user"

    def _systemctl_env(self) -> dict:
        env = dict(os.environ)
        env.setdefault("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
        return env

    def _systemctl(self, *args: str) -> list[str]:
        return ["systemctl", "--user", *args]

    def _render_unit(self) -> str:
        root = cli_root()
        return MONITOR_DAEMON_TEMPLATE.format(
            bench_name=self.bench.config.name,
            cli_root=root,
            bench_root=self.bench.path,
            bench_logs=self.bench.logs_path,
            python=AdminEnvManager(root).python,
        )

    def _write_unit(self) -> None:
        self.monitor_service_path.parent.mkdir(parents=True, exist_ok=True)
        self.monitor_service_path.write_text(self._render_unit())

    def _install_user_unit(self) -> None:
        self.user_unit_dir.mkdir(parents=True, exist_ok=True)
        link = self.user_unit_dir / self.unit_name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(self.monitor_service_path.resolve())

    def install(self) -> None:
        self._write_unit()
        self._install_user_unit()

        # Keep the user manager running after logout so the daemon survives, then
        # make sure it's up before talking to `systemctl --user`.
        subprocess.run(
            ["sudo", "loginctl", "enable-linger", getpass.getuser()],
            capture_output=True,
            check=False,
        )
        subprocess.run(
            ["sudo", "systemctl", "start", f"user@{os.getuid()}.service"],
            capture_output=True,
            check=False,
        )

        env = self._systemctl_env()
        run_command(self._systemctl("daemon-reload"), env=env)
        run_command(self._systemctl("enable", "--now", self.unit_name), env=env)


class Monitor:
    """Implementation class for monitoring fetches and stores the details found in the

    `path/to/monitor.json`
    """

    def __init__(self):
        ...