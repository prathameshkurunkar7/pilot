from __future__ import annotations

from pilot.config.bench import BenchConfig
from pilot.config.waf import (
    WAF_MODES,
    WAF_RULE_ACTIONS,
    WAF_RULE_FIELDS,
    WAF_RULE_MATCH,
    WAF_RULE_OPERATORS,
)
from pilot.managers.platform import is_linux, native_process_manager
from pilot.managers.redis import RedisManager
from pilot.managers.waf import WafManager

_RESTART_KEYS = {
    ("bench", "python"),
    ("bench", "http_port"),
    ("bench", "socketio_port"),
    ("mariadb", "host"),
    ("mariadb", "port"),
    ("mariadb", "admin_user"),
    ("mariadb", "socket_path"),
    # postgres is intentionally absent: its connection is read fresh by the
    # new-site subprocess, so no running process needs restarting on a change.
    ("redis", "cache_port"),
    ("redis", "queue_port"),
    ("workers", "groups"),
    ("production", "process_manager"),
}


def _needs_restart(old: dict, new: dict) -> bool:
    return any(
        old.get(section, {}).get(key) != new.get(section, {}).get(key)
        for section, key in _RESTART_KEYS
    )


def _worker_groups_payload(config: BenchConfig) -> list[dict]:
    return [{"queues": list(group.queues), "count": group.count} for group in config.workers.groups]


def _firewall_payload(config: BenchConfig) -> dict:
    firewall = config.firewall
    return {
        "enabled": firewall.enabled,
        "default": firewall.default,
        "rules": [
            {"ip": rule.ip, "action": rule.action, "description": rule.description}
            for rule in firewall.rules
        ],
    }


def _waf_payload(config: BenchConfig) -> dict:
    waf = config.waf
    return {
        "enabled": waf.enabled,
        "mode": waf.mode,
        "paranoia": waf.paranoia,
        "inbound_threshold": waf.inbound_threshold,
        "body_limit": waf.body_limit,
        "inspect_responses": waf.inspect_responses,
        "exclusions": list(waf.exclusions),
        "exempt_paths": list(waf.exempt_paths),
        "custom_rules": [
            {
                "name": rule.name,
                "action": rule.action,
                "match": rule.match,
                "enabled": rule.enabled,
                "conditions": [
                    {
                        "field": condition.field,
                        "operator": condition.operator,
                        "value": condition.value,
                        "header_name": condition.header_name,
                    }
                    for condition in rule.conditions
                ],
            }
            for rule in waf.custom_rules
        ],
    }


def _s3_payload(config: BenchConfig) -> dict:
    return {
        "access_key": config.s3.access_key,
        "secret_key_set": bool(config.s3.secret_key),
        "bucket": config.s3.bucket,
        "provider": config.s3.provider,
        "region": config.s3.region,
    }


def _s3_provider_options() -> list[dict]:
    from pilot.integrations.s3.base import PROVIDER_LABELS, SUPPORTED_REGIONS

    return [
        {"value": provider, "label": PROVIDER_LABELS[provider], "regions": regions}
        for provider, regions in SUPPORTED_REGIONS.items()
    ]


def _restart_trigger_values(config: BenchConfig) -> dict:
    return {
        "bench": {
            "python": config.python_version,
            "http_port": config.http_port,
            "socketio_port": config.socketio_port,
        },
        "mariadb": {
            "host": config.mariadb.host,
            "port": config.mariadb.port,
            "admin_user": config.mariadb.admin_user,
            "socket_path": config.mariadb.socket_path,
        },
        "redis": {"cache_port": config.redis.cache_port, "queue_port": config.redis.queue_port},
        "workers": {"groups": _worker_groups_payload(config)},
        "production": {"process_manager": config.production.process_manager or "none"},
    }


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
