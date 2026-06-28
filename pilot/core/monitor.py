"""This module houses the light-weight monitoring daemon that will utilise /proc
- Dump them into a bench-stats.json present inside the bench
- Logrotate the bench-stats.json file
"""

import getpass
import json
import os
import re
import subprocess
import typing
from datetime import datetime
from pathlib import Path

from pilot.exceptions import BenchError
from pilot.loader import cli_root
from pilot.managers.admin_env_manager import AdminEnvManager
from pilot.managers.process_manager import ProcessManagerFactory
from pilot.platform import is_linux
from pilot.utils import run_command

if typing.TYPE_CHECKING:
    from pilot.core.bench import Bench
    from pilot.managers.supervisor_process_manager import SupervisorProcessManager
    from pilot.managers.systemd_process_manager import SystemdProcessManager

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

SUPERVISOR_PROCESS_PATTERN = re.compile(r"^(?P<service>\S+)\s+RUNNING\s+pid\s+(?P<pid>\d+)", re.MULTILINE)
SYSTEMD_PID_PATTERN = re.compile(r"^MainPID=(?P<pid>\d+)", re.MULTILINE)


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


class ToMonitor:
    def __init__(self, bench: "Bench"):
        self.bench = bench
        self.admin_service_name = f"{self.bench.config.name}-admin"

    def systemd_processes(self):
        bench_process_manager: SystemdProcessManager = ProcessManagerFactory.create(self.bench)
        systemd_dir = self.bench.config_path / "systemd"

        if not systemd_dir.exists():
            return {}

        services = [
            service.name
            for service in systemd_dir.iterdir()
            if service.name.endswith(".service") and service.name != f"{self.admin_service_name}.service"
        ]

        if not services:
            return {}

        pids = {}
        env = bench_process_manager._systemctl_env()
        cmd = bench_process_manager._systemctl("show", "--property", "MainPID", *services)

        output = run_command(cmd, env=env).stdout.decode().strip()
        pid_matches = SYSTEMD_PID_PATTERN.finditer(output)

        for service, match in zip(services, pid_matches):
            pid_val = int(match.group("pid"))
            if pid_val > 0:
                pids[service] = pid_val

        return pids

    def supervisord_processes(self):
        pids = {}
        bench_process_manager: SupervisorProcessManager = ProcessManagerFactory.create(self.bench)

        result = run_command(["supervisorctl", "-c", bench_process_manager.supervisor_conf_path, "status"])
        supervised_processes = result.stdout.decode().strip()

        # Optimize matching loop by extracting specific named groups directly
        for match in SUPERVISOR_PROCESS_PATTERN.finditer(supervised_processes):
            service_name = match.group("service")

            if service_name != self.admin_service_name:
                pids[service_name] = int(match.group("pid"))

        return pids

    def to_monitor(self):
        prod_config = self.bench.config.production
        if not prod_config.enabled:
            return []

        manager_mapping = {"systemd": self.systemd_processes, "supervisor": self.supervisord_processes}

        monitor_func = manager_mapping.get(prod_config.process_manager)
        return monitor_func() if monitor_func else {}


class Monitor:
    """Implementation class for monitoring fetches and stores the details found in the proc dir"""

    def __init__(self, bench: "Bench"):
        self.bench = bench
        self._cpu_snapshots: dict[int, tuple[int, int]] = {}
        self.setup()

    def _create_log_dataset_if_required(self) -> None:
        from pilot.managers.volume_manager import VolumeManager

        volume = self.bench.config.volume
        VolumeManager(volume).create_dataset(f"{volume.pool}/logs")

    @property
    def logs_path(self) -> Path:
        bench_name = self.bench.config.name
        if self.bench.config.volume.enabled:
            self._create_log_dataset_if_required()
            from pilot.managers.volume_manager import VolumeManager

            volume = self.bench.config.volume
            mountpoint = VolumeManager(volume).get_mountpoint(f"{volume.pool}/logs")
            return mountpoint / f"{bench_name}-stats.log"
        return Path(f"/var/log/{bench_name}-stats.log")

    def setup_log_rotation(self) -> None:
        """Log size per bench for now is 500M we can expose via settings later"""
        log_file = self.logs_path
        config = f"""\
{log_file} {{
    size 500M
    rotate 3
    compress
    missingok
    notifempty
    copytruncate
}}
"""
        config_path = Path(f"/etc/logrotate.d/{self.bench.config.name}-stats")
        subprocess.run(["sudo", "tee", str(config_path)], input=config.encode(), capture_output=True, check=True)

    def setup(self) -> None:
        if not is_linux():
            BenchError("Monitoring is only supported on linux based machines.")

        log_dir = self.logs_path.parent
        log_dir.mkdir(parents=True, exist_ok=True)
        subprocess.run(["sudo", "chown", f"{os.getuid()}:{os.getgid()}", str(log_dir)], check=True)
        self.setup_log_rotation()

    def _total_cpu_ticks(self) -> int:
        line = Path("/proc/stat").read_text().splitlines()[0]
        return sum(int(x) for x in line.split()[1:])

    def _cpu_percent(self, pid: int) -> float:
        fields = Path(f"/proc/{pid}/stat").read_text().split()
        cpu_ticks = int(fields[13]) + int(fields[14])
        total_ticks = self._total_cpu_ticks()
        prev = self._cpu_snapshots.get(pid)
        self._cpu_snapshots[pid] = (cpu_ticks, total_ticks)
        if prev is None:
            return 0.0
        delta_cpu = cpu_ticks - prev[0]
        delta_total = total_ticks - prev[1]
        return round(delta_cpu / delta_total * 100, 2) if delta_total > 0 else 0.0

    def _read_status(self, pid: int) -> dict[str, str]:
        lines = Path(f"/proc/{pid}/status").read_text().splitlines()
        return {k: v.strip() for k, v in (line.split(":", 1) for line in lines if ":" in line)}

    def _io_bytes(self, pid: int) -> tuple[int, int]:
        lines = Path(f"/proc/{pid}/io").read_text().splitlines()
        data = {k: int(v) for k, v in (line.split(": ", 1) for line in lines if ": " in line)}
        return data.get("read_bytes", 0), data.get("write_bytes", 0)

    def _open_fds(self, pid: int) -> int:
        try:
            return len(list(Path(f"/proc/{pid}/fd").iterdir()))
        except PermissionError:
            return -1

    def _process_metrics(self, service: str, pid: int) -> dict:
        status = self._read_status(pid)
        read_bytes, write_bytes = self._io_bytes(pid)
        return {
            "service": service,
            "pid": pid,
            "state": status.get("State", "?").split()[0],
            "cpu_percent": self._cpu_percent(pid),
            "memory_rss_mb": round(int(status.get("VmRSS", "0 kB").split()[0]) / 1024, 2),
            "read_bytes": read_bytes,
            "write_bytes": write_bytes,
            "open_fds": self._open_fds(pid),
        }

    def collect(self) -> dict:
        processes = []
        for service, pid in ToMonitor(self.bench).to_monitor().items():
            if not Path(f"/proc/{pid}").exists():
                processes.append({"service": service, "pid": pid, "missing": True})
                continue
            processes.append(self._process_metrics(service, pid))
        return {"bench": self.bench.config.name, "processes": processes}

    def dump(self) -> None:
        path = self.logs_path
        stats = json.loads(path.read_text()) if path.exists() else {}
        stats[datetime.now().isoformat()] = self.collect()
        path.write_text(json.dumps(stats, indent=2))


def main(bench_name: Path) -> None:
    from pilot.core.bench import Bench, BenchConfig

    bench_root = cli_root() / "benches" / bench_name
    bench = Bench(BenchConfig.from_file(bench_root / "bench.toml"), bench_root)
    monitor = Monitor(bench=bench)
    monitor.dump()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m pilot.core.monitor <bench_root>")

    main(Path(sys.argv[1]))
