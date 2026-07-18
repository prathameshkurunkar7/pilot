from __future__ import annotations

from pilot.config import BenchConfig
from pilot.config import (
    WAF_MODES,
    WAF_RULE_ACTIONS,
    WAF_RULE_FIELDS,
    WAF_RULE_MATCH,
    WAF_RULE_OPERATORS,
)
from pilot.managers.platform import is_linux, native_process_manager
from pilot.managers.redis import RedisManager
from pilot.managers.waf import WafManager
from pilot.core.bench.settings import (
    firewall_payload as _firewall_payload,
    needs_restart as _needs_restart,
    restart_trigger_values as _restart_trigger_values,
    s3_payload as _s3_payload,
    waf_payload as _waf_payload,
    worker_groups_payload as _worker_groups_payload,
)

__all__ = [
    "_build_settings_response",
    "_firewall_payload",
    "_needs_restart",
    "_restart_trigger_values",
    "_s3_payload",
    "_waf_payload",
]


def _s3_provider_options() -> list[dict]:
    from pilot.integrations.s3.base import PROVIDER_LABELS, SUPPORTED_REGIONS

    return [
        {"value": provider, "label": PROVIDER_LABELS[provider], "regions": regions}
        for provider, regions in SUPPORTED_REGIONS.items()
    ]


def _build_settings_response(config: BenchConfig) -> dict:
    return {
        "is_linux": is_linux(),
        "native_process_manager": native_process_manager(),
        "bench": {
            "name": config.name,
            "python": config.python_version,
            "http_port": config.http_port,
            "socketio_port": config.socketio_port,
            "default_branch": config.default_branch,
            "db_type": config.db_type,
        },
        "mariadb": {
            "host": config.mariadb.host,
            "port": config.mariadb.port,
            "admin_user": config.mariadb.admin_user,
            "socket_path": config.mariadb.socket_path,
        },
        "postgres": {
            "host": config.postgres.host,
            "port": config.postgres.port,
            "admin_user": config.postgres.admin_user,
            "password_set": bool(config.postgres.root_password),
        },
        "redis": {
            "cache_port": config.redis.cache_port,
            "queue_port": config.redis.queue_port,
            "version": RedisManager.installed_version() or config.redis.version or "",
        },
        "workers": _worker_groups_payload(config),
        "firewall": _firewall_payload(config),
        "waf": {
            **_waf_payload(config),
            "installed": WafManager.is_installed(),
            "modes": list(WAF_MODES),
            "rule_fields": list(WAF_RULE_FIELDS),
            "rule_operators": list(WAF_RULE_OPERATORS),
            "rule_actions": list(WAF_RULE_ACTIONS),
            "rule_match": list(WAF_RULE_MATCH),
        },
        "production": {
            "process_manager": config.production.process_manager or "none",
            "enabled": config.production.enabled,
        },
        "admin": {"domain": config.admin.domain, "tls": config.admin.tls},
        "letsencrypt": {"email": config.letsencrypt.email},
        "s3": _s3_payload(config),
        "s3_providers": _s3_provider_options(),
        "monitor": {
            "system_log_path": str(config.monitor.system_log_path),
            "log_path": str(config.monitor.log_path) if config.monitor.log_path else "",
            "system_log_max_size": config.monitor.system_log_max_size,
            "application_log_max_size": config.monitor.application_log_max_size,
        },
    }
