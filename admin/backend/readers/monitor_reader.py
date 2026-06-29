from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

WINDOW_SECONDS = {"30m": 1800, "1h": 3600, "6h": 21600, "12h": 43200, "24h": 86400, "1w": 604800}
MAX_POINTS = 400
DISK_SERIES = "Root Disk"


class MonitorHistoryReader:
    """Renders time-series from the monitor log files for a selected window.

    System metrics live in a shared log; application metrics in a per-bench log.
    Each file is a JSON object keyed by ISO timestamp.
    """

    def __init__(self, bench_root: Path, window: str) -> None:
        self._bench_root = bench_root
        self._window = window if window in WINDOW_SECONDS else "1h"
        self._cutoff = datetime.now() - timedelta(seconds=WINDOW_SECONDS[self._window])

    def read(self) -> dict:
        from pilot.config.monitor_config import MonitorConfig
        from pilot.config.toml_store import BenchTomlStore

        config = BenchTomlStore.for_bench(self._bench_root).read()
        app_log = config.monitor.log_path or MonitorConfig.default_log_path(config.name)
        return {
            "window": self._window,
            "window_seconds": WINDOW_SECONDS[self._window],
            # Absolute epoch ms so the browser windows correctly regardless of its
            # timezone — log timestamps are naive (server-local).
            "now": int(datetime.now().timestamp() * 1000),
            "system": self._system(config.monitor.system_log_path),
            "application": self._application(app_log, config.name),
        }

    def _system(self, path: Path) -> dict:
        raw = self._load(path)
        rows = self._within_window(raw)
        storage = self._latest_storage(rows)
        pool = storage["zfs"]["pool"] if storage and storage["zfs"] else None
        return {
            "earliest": self._earliest(raw),
            "points": [self._system_point(when, metrics, pool) for when, metrics in rows],
            "storage": storage,
        }

    def _system_point(self, when: datetime, metrics: dict, pool: str | None) -> dict:
        storage = metrics.get("storage") or {}
        disk, zfs = storage.get("disk"), storage.get("zfs")
        point = {
            "time": self._ms(when),
            "CPU": metrics.get("cpu_percent", 0),
            "Memory": metrics.get("memory", {}).get("percent", 0),
            "Load1": self._load_at(metrics, 0),
            "Load5": self._load_at(metrics, 1),
            "Load15": self._load_at(metrics, 2),
            DISK_SERIES: disk.get("percent") if disk else None,
        }
        if pool:
            point[pool] = zfs.get("percent") if zfs else None
        return point

    @classmethod
    def _latest_storage(cls, rows: list) -> dict | None:
        # `disk` is always recorded; `zfs` only when the bench is volume-backed.
        for _, metrics in reversed(rows):
            storage = metrics.get("storage")
            if storage and storage.get("disk"):
                return {"disk": cls._slim(storage["disk"]), "zfs": cls._slim_zfs(storage.get("zfs"))}
        return None

    @staticmethod
    def _slim(entry: dict) -> dict:
        return {"used_mb": entry.get("used_mb"), "total_mb": entry.get("total_mb"), "percent": entry.get("percent")}

    @classmethod
    def _slim_zfs(cls, zfs: dict | None) -> dict | None:
        return {"pool": zfs.get("pool"), **cls._slim(zfs)} if zfs else None

    def _application(self, path: Path, bench_name: str) -> dict:
        raw = self._load(path)
        rows = self._within_window(raw)
        return {
            "earliest": self._earliest(raw),
            "services": self._service_names(rows, bench_name),
            "cpu": [self._service_row(when, metrics, bench_name, "cpu_percent") for when, metrics in rows],
            "memory": [self._service_row(when, metrics, bench_name, "memory_rss_mb") for when, metrics in rows],
        }

    def _within_window(self, raw: dict) -> list[tuple[datetime, dict]]:
        rows = []
        for timestamp, metrics in raw.items():
            when = self._parse(timestamp)
            if when and when >= self._cutoff:
                rows.append((when, metrics))
        rows.sort(key=lambda row: row[0])
        return self._downsample(rows)

    def _service_names(self, rows: list, bench_name: str) -> list[str]:
        names: list[str] = []
        for _, metrics in rows:
            for process in metrics.get("processes", []):
                short = self._short(process["service"], bench_name)
                if short not in names:
                    names.append(short)
        return sorted(names)

    def _service_row(self, when: datetime, metrics: dict, bench_name: str, key: str) -> dict:
        row = {"time": self._ms(when)}
        for process in metrics.get("processes", []):
            if not process.get("missing"):
                row[self._short(process["service"], bench_name)] = process.get(key, 0)
        return row

    @staticmethod
    def _short(service: str, bench_name: str) -> str:
        return service.removeprefix(f"{bench_name}-").removesuffix(".service")

    @staticmethod
    def _load_at(metrics: dict, index: int) -> float:
        load = metrics.get("load_avg") or []
        return load[index] if index < len(load) else 0

    @staticmethod
    def _load(path: Path) -> dict:
        if not path.exists():
            return {}
        try:
            return json.loads(path.read_text())
        except (ValueError, OSError):
            return {}

    @staticmethod
    def _parse(timestamp: str) -> datetime | None:
        try:
            return datetime.fromisoformat(timestamp)
        except ValueError:
            return None

    @staticmethod
    def _downsample(rows: list) -> list:
        if len(rows) <= MAX_POINTS:
            return rows
        step = len(rows) // MAX_POINTS + 1
        return rows[::step]

    @classmethod
    def _earliest(cls, raw: dict) -> int | None:
        keys = sorted(raw.keys())
        when = cls._parse(keys[0]) if keys else None
        return cls._ms(when) if when else None

    @staticmethod
    def _ms(when: datetime) -> int:
        return int(when.timestamp() * 1000)
