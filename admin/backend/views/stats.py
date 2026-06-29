from __future__ import annotations

import subprocess
from dataclasses import asdict
from functools import lru_cache
from pathlib import Path

import psutil
from flask import Blueprint, current_app, jsonify, request

from pilot.config.bench_config import BenchConfig
from pilot.config.toml_store import BenchTomlStore
from ..readers.volume_reader import VolumeReader

stats_bp = Blueprint("stats", __name__)


@lru_cache(maxsize=16)
def _directory_size(path: str) -> int:
    try:
        result = subprocess.run(["du", "-sb", path], capture_output=True, timeout=10)
        return int(result.stdout.split()[0]) if result.returncode == 0 else 0
    except Exception:
        return 0


def _path_sizes(bench_root: Path, config: BenchConfig) -> list[dict]:
    from pilot.managers.mariadb_manager import MariaDBManager

    benches_dir = str(bench_root)
    mariadb = MariaDBManager(config.mariadb)
    mariadb_dir = mariadb.data_dir() if mariadb.is_dedicated else "/var/lib/mysql"
    return [
        {"label": "Benches", "path": benches_dir, "used_bytes": _directory_size(benches_dir)},
        {"label": "MariaDB", "path": mariadb_dir, "used_bytes": _directory_size(mariadb_dir)},
    ]


def _log_file_info(description: str, path: Path) -> dict:
    from datetime import datetime, timezone
    if path.exists():
        last_modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")
    else:
        last_modified = None
    return {"description": description, "path": str(path), "last_modified": last_modified}


@stats_bp.route("/monitor-status")
def get_monitor_status():
    from pilot.config.monitor_config import MonitorConfig
    from pilot.config.toml_store import BenchTomlStore
    bench_root = Path(current_app.config["BENCH_ROOT"])
    try:
        config = BenchTomlStore.for_bench(bench_root).read()
        mon = config.monitor
        log_path = mon.log_path or MonitorConfig.default_log_path(config.name)
        return jsonify([
            _log_file_info("System Log", mon.system_log_path),
            _log_file_info("Application Log", log_path),
        ])
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@stats_bp.route("/monitor-history")
def get_monitor_history():
    from ..readers.monitor_reader import MonitorHistoryReader

    bench_root = Path(current_app.config["BENCH_ROOT"])
    window = request.args.get("window", "1h")
    try:
        return jsonify(MonitorHistoryReader(bench_root, window).read())
    except Exception as error:
        return jsonify({"error": str(error)}), 500


@stats_bp.route("/stats")
def stats():
    bench_root = current_app.config["BENCH_ROOT"]
    config = BenchTomlStore.for_bench(bench_root).read()
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    volume = VolumeReader(bench_root).read()
    paths = _path_sizes(bench_root, config) if not volume.enabled else []
    return jsonify(
        {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": mem.percent,
            "memory_used": mem.total - mem.available,
            "memory_total": mem.total,
            "disk_percent": disk.percent,
            "disk_used": disk.used,
            "disk_total": disk.total,
            "volume": asdict(volume),
            "paths": paths,
        }
    )
