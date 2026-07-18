from __future__ import annotations

import subprocess
from pathlib import Path

from pilot.config import BenchConfig
from pilot.core.bench import Bench
from pilot.managers.waf import WafManager

from admin.backend.api.v1.settings_payload import (
    _firewall_payload,
    _needs_restart,
    _restart_trigger_values,
    _s3_payload,
    _waf_payload,
)


class _SettingsApplyFailed(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _non_admin_supervisor_programs(conf: Path, bench_name: str) -> list[str]:
    result = subprocess.run(
        ["supervisorctl", "-c", str(conf), "status", f"{bench_name}:*"],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return [
        line.split()[0]
        for line in result.stdout.splitlines()
        if line.strip() and not line.split()[0].endswith("-admin")
    ]


def _regenerate_configs(bench_root: Path, config: BenchConfig) -> None:
    from pilot.managers.processes.local import ProcessManager
    from pilot.managers.redis import RedisManager

    bench = Bench(config, bench_root)
    RedisManager(config.redis, bench).generate_configs()
    ProcessManager.for_bench(bench).write_config()


def _regenerate_nginx(bench_root: Path, config: BenchConfig) -> None:
    from pilot.managers.nginx import NginxManager

    bench = Bench(config, bench_root)
    manager = NginxManager(bench)
    manager.generate_config(ssl_ready=True)
    manager.install_config()


def _restart_supervisor(manager, bench_name: str) -> bool:
    if not manager.is_alive():
        return False
    subprocess.run(
        [*manager._supervisorctl(), "reread"],
        capture_output=True,
        timeout=10,
        check=True,
    )
    subprocess.run(
        [*manager._supervisorctl(), "update"],
        capture_output=True,
        timeout=10,
        check=True,
    )
    programs = _non_admin_supervisor_programs(manager.supervisor_conf_path, bench_name)
    if not programs:
        return False
    subprocess.run(
        [*manager._supervisorctl(), "restart", *programs],
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    return True


def _restart_systemd(manager) -> bool:
    if not manager.is_running():
        return False
    env = manager._systemctl_env()
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        capture_output=True,
        env=env,
        timeout=10,
        check=True,
    )
    non_admin_units = [
        manager._unit_name(process.name)
        for process in manager._prod_process_definitions()
        if process.name != "admin"
    ]
    if not non_admin_units:
        return False
    subprocess.run(
        [*manager._systemctl(), "restart", *non_admin_units],
        capture_output=True,
        text=True,
        timeout=60,
        env=env,
        check=True,
    )
    return True


def _do_restart(bench_root: Path, config: BenchConfig) -> bool:
    from pilot.managers.processes.local import ProcessManager
    from pilot.managers.processes.supervisor import SupervisorProcessManager
    from pilot.managers.processes.systemd import SystemdProcessManager

    bench = Bench(config, bench_root)
    manager = ProcessManager.detect_running(bench)
    if isinstance(manager, SupervisorProcessManager):
        return _restart_supervisor(manager, config.name)
    if isinstance(manager, SystemdProcessManager):
        return _restart_systemd(manager)
    return False


def _apply_post_save_changes(
    bench_root: Path,
    config: BenchConfig,
    old_restart: dict,
    old_firewall: dict,
    old_waf: dict,
    old_s3_config: dict,
) -> tuple[bool, str | None]:
    restarted = False
    if _needs_restart(old_restart, _restart_trigger_values(config)):
        try:
            _regenerate_configs(bench_root, config)
        except Exception as error:
            raise _SettingsApplyFailed(
                "configuration_generation_failed",
                "Settings were saved, but service configuration could not be regenerated.",
            ) from error
        try:
            restarted = _do_restart(bench_root, config)
        except Exception as error:
            raise _SettingsApplyFailed(
                "service_restart_failed",
                "Settings were saved, but running services could not be restarted.",
            ) from error

    waf_changed = _waf_payload(config) != old_waf
    waf_warning = None
    if config.production.enabled and (_firewall_payload(config) != old_firewall or waf_changed):
        if waf_changed and config.waf.enabled and not WafManager.is_installed():
            waf_warning = (
                "ModSecurity is not installed on this host. Redeploy production to "
                "install the WAF; it stays inactive until then."
            )
        try:
            _regenerate_nginx(bench_root, config)
        except Exception as error:
            raise _SettingsApplyFailed(
                "nginx_apply_failed",
                "Settings were saved, but nginx could not apply them.",
            ) from error

    if _s3_payload(config) != old_s3_config:
        try:
            bench = Bench(BenchConfig.from_file(bench_root / "bench.toml"), bench_root)
            bench.sync_s3_credentials(config.s3)
        except Exception as error:
            raise _SettingsApplyFailed(
                "s3_sync_failed",
                "Settings were saved, but site backup configuration could not be synchronized.",
            ) from error

    return restarted, waf_warning
