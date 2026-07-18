from __future__ import annotations

from pathlib import Path

from pilot.config import BenchConfig
from pilot.core.bench import Bench
from pilot.core.bench.settings import (
    SettingsApplyFailed as _SettingsApplyFailed,
    regenerate_configs as _regenerate_configs,
    regenerate_nginx as _regenerate_nginx,
    restart_running_workload as _do_restart,
)

__all__ = [
    "_SettingsApplyFailed",
    "_apply_post_save_changes",
    "_do_restart",
    "_regenerate_configs",
    "_regenerate_nginx",
]


def _apply_post_save_changes(
    bench_root: Path,
    config: BenchConfig,
    old_restart: dict,
    old_firewall: dict,
    old_waf: dict,
    old_s3_config: dict,
) -> tuple[bool, str | None]:
    return Bench(config, bench_root).apply_saved_settings(
        old_restart,
        old_firewall,
        old_waf,
        old_s3_config,
    )
