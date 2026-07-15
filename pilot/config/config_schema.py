from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields

from pilot.config.admin_config import AdminConfig
from pilot.config.app_config import AppConfig
from pilot.config.central_config import CentralConfig
from pilot.config.firewall_config import FirewallConfig, FirewallRule
from pilot.config.gunicorn_config import GunicornConfig
from pilot.config.letsencrypt_config import LetsEncryptConfig
from pilot.config.mariadb_config import MariaDBConfig
from pilot.config.monitor_config import MonitorConfig
from pilot.config.nginx_config import NginxConfig
from pilot.config.postgres_config import PostgresConfig
from pilot.config.production_config import ProductionConfig
from pilot.config.redis_config import RedisConfig
from pilot.config.s3_config import S3Config
from pilot.config.worker_config import WorkerGroup


@dataclass
class _Table:
    """Declared shape of one bench.toml table: its accepted leaf keys plus any
    nested tables and arrays-of-tables. Drives unknown-field detection."""

    keys: set[str] = field(default_factory=set)
    tables: dict[str, "_Table"] = field(default_factory=dict)
    arrays: dict[str, "_Table"] = field(default_factory=dict)


def _keys(dataclass_type: type) -> set[str]:
    return {f.name for f in fields(dataclass_type)}


# The [bench] table flattens top-level fields whose keys differ from the
# BenchConfig attribute names (python vs python_version), so it is listed here.
_BENCH_KEYS = {
    "name",
    "python",
    "http_port",
    "socketio_port",
    "socketio_backend",
    "watch_apps_js",
    "reload_python",
    "watch_admin_js",
    "db_type",
    "default_branch",
}
# Keys older bench-cli versions wrote that the parser still tolerates.
_PRODUCTION_LEGACY = {"lightweight", "nginx"}
_WORKER_LEGACY = {"queue"}


def _bench_schema() -> _Table:
    return _Table(
        tables={
            "bench": _Table(keys=set(_BENCH_KEYS)),
            "mariadb": _Table(keys=_keys(MariaDBConfig)),
            "postgres": _Table(keys=_keys(PostgresConfig)),
            "redis": _Table(keys=_keys(RedisConfig)),
            "production": _Table(keys=_keys(ProductionConfig) | _PRODUCTION_LEGACY),
            "monitor": _Table(keys=_keys(MonitorConfig)),
            "nginx": _Table(keys=_keys(NginxConfig)),
            "gunicorn": _Table(keys=_keys(GunicornConfig)),
            "letsencrypt": _Table(keys=_keys(LetsEncryptConfig)),
            "admin": _Table(keys=_keys(AdminConfig)),
            "central": _Table(keys=_keys(CentralConfig)),
            "s3": _Table(keys=_keys(S3Config)),
            "firewall": _Table(
                keys=_keys(FirewallConfig) - {"rules"},
                arrays={"rules": _Table(keys=_keys(FirewallRule))},
            ),
        },
        arrays={
            "apps": _Table(keys=_keys(AppConfig)),
            "workers": _Table(keys=_keys(WorkerGroup) | _WORKER_LEGACY),
        },
    )


_ROOT = _bench_schema()


def unknown_config_paths(data: Mapping) -> list[str]:
    """Dotted paths of every bench.toml key the schema does not declare, e.g.
    ``mariadb.typo`` or an unknown top-level table ``whatever``."""
    return _scan(data, _ROOT, "")


def _scan(data: Mapping, table: _Table, prefix: str) -> list[str]:
    unknown: list[str] = []
    for key, value in data.items():
        path = f"{prefix}{key}"
        if key in table.tables and isinstance(value, Mapping):
            unknown += _scan(value, table.tables[key], f"{path}.")
        elif key in table.arrays and isinstance(value, list):
            unknown += _scan_array(value, table.arrays[key], path)
        elif key not in table.keys and key not in table.tables and key not in table.arrays:
            unknown.append(path)
    return unknown


def _scan_array(entries: list, table: _Table, path: str) -> list[str]:
    unknown: list[str] = []
    for index, entry in enumerate(entries):
        if isinstance(entry, Mapping):
            unknown += _scan(entry, table, f"{path}[{index}].")
    return unknown
