from __future__ import annotations

from pathlib import Path

from pilot.config.bench import BenchConfig
from pilot.config.waf import WafConfig
from pilot.internal.toml import ConfigDict, Toml, TomlDataclassCodec


def _bench_config_from_dict(data: ConfigDict, *, strict: bool = False) -> BenchConfig:
    return BenchConfig._from_dict(data, strict=strict)


def _bench_config_to_dict(config: BenchConfig) -> ConfigDict:
    data: ConfigDict = {
        "bench": _bench_section(config),
        "apps": _apps_section(config),
        "mariadb": _mariadb_section(config),
        "postgres": _postgres_section(config),
        "redis": _redis_section(config),
        "workers": _workers_section(config),
        "production": _production_section(config),
        "gunicorn": _gunicorn_section(config),
        "letsencrypt": _letsencrypt_section(config),
        "admin": _admin_section(config),
    }
    _add_optional_sections(data, config)
    return data


def _bench_section(config: BenchConfig) -> ConfigDict:
    bench: ConfigDict = {
        "name": config.name,
        "python": config.python_version,
        "http_port": config.http_port,
        "socketio_port": config.socketio_port,
        "socketio_backend": config.socketio_backend,
        "watch_apps_js": config.watch_apps_js,
        "reload_python": config.reload_python,
        "watch_admin_js": config.watch_admin_js,
        "db_type": config.db_type,
    }
    if config.default_branch:
        bench["default_branch"] = config.default_branch
    return bench


def _apps_section(config: BenchConfig) -> list[ConfigDict]:
    apps: list[ConfigDict] = []
    for app in config.apps:
        app_data: ConfigDict = {"name": app.name, "repo": app.repo, "branch": app.branch}
        if app.branches:
            app_data["branches"] = app.branches
        apps.append(app_data)
    return apps


def _mariadb_section(config: BenchConfig) -> ConfigDict:
    return {
        "host": config.mariadb.host,
        "port": config.mariadb.port,
        "root_password": config.mariadb.root_password,
        "admin_user": config.mariadb.admin_user,
        "socket_path": config.mariadb.socket_path,
        "existing": config.mariadb.existing,
    }


def _postgres_section(config: BenchConfig) -> ConfigDict:
    return {
        "host": config.postgres.host,
        "port": config.postgres.port,
        "root_password": config.postgres.root_password,
        "admin_user": config.postgres.admin_user,
        "existing": config.postgres.existing,
    }


def _redis_section(config: BenchConfig) -> ConfigDict:
    redis: ConfigDict = {
        "cache_port": config.redis.cache_port,
        "queue_port": config.redis.queue_port,
    }
    if config.redis.version:
        redis["version"] = config.redis.version
    return redis


def _workers_section(config: BenchConfig) -> list[ConfigDict]:
    return [{"queues": group.queues, "count": group.count} for group in config.workers.groups]


def _production_section(config: BenchConfig) -> ConfigDict:
    production: ConfigDict = {
        "enabled": config.production.enabled,
        "use_companion_manager": config.production.use_companion_manager,
    }
    if config.production.process_manager:
        production["process_manager"] = config.production.process_manager
    return production


def _gunicorn_section(config: BenchConfig) -> ConfigDict:
    return {
        "workers": config.gunicorn.workers,
        "threads": config.gunicorn.threads,
        "timeout": config.gunicorn.timeout,
        "worker_class": config.gunicorn.worker_class,
        "malloc_arena_max": config.gunicorn.malloc_arena_max or 2,
        "max_requests": config.gunicorn.max_requests,
        "max_requests_jitter": config.gunicorn.max_requests_jitter,
    }


def _letsencrypt_section(config: BenchConfig) -> ConfigDict:
    return {
        "email": config.letsencrypt.email,
        "webroot_path": str(config.letsencrypt.webroot_path),
    }


def _admin_section(config: BenchConfig) -> ConfigDict:
    admin: ConfigDict = {
        "port": config.admin.port,
        "timeout": config.admin.timeout,
        "enabled": config.admin.enabled,
        "password": config.admin.password,
        "domain": config.admin.domain,
        "tls": config.admin.tls,
        "allow_bench_management": config.admin.allow_bench_management,
    }
    optional_admin = {
        "jwt_secret": config.admin.jwt_secret,
        "jwks_url": config.admin.jwks_url,
        "jwks_audience": config.admin.jwks_audience,
    }
    admin.update({key: value for key, value in optional_admin.items() if value})
    return admin


def _add_optional_sections(data: ConfigDict, config: BenchConfig) -> None:
    if config.central.endpoint or config.central.auth_token:
        data["central"] = {
            "endpoint": config.central.endpoint,
            "auth_token": config.central.auth_token,
        }

    if config.firewall.enabled or config.firewall.rules:
        data["firewall"] = {
            "enabled": config.firewall.enabled,
            "default": config.firewall.default,
            "rules": [
                {
                    "ip": rule.ip,
                    "action": rule.action,
                    "description": rule.description,
                }
                for rule in config.firewall.rules
            ],
        }

    waf = config.waf
    if waf != WafConfig():
        data["waf"] = {
            "enabled": waf.enabled,
            "mode": waf.mode,
            "paranoia": waf.paranoia,
            "inbound_threshold": waf.inbound_threshold,
            "body_limit": waf.body_limit,
            "inspect_responses": waf.inspect_responses,
            "exclusions": waf.exclusions,
            "exempt_paths": waf.exempt_paths,
            "custom_rules": [
                {
                    "name": rule.name,
                    "action": rule.action,
                    "match": rule.match,
                    "enabled": rule.enabled,
                    "conditions": [
                        {
                            "field": c.field,
                            "operator": c.operator,
                            "value": c.value,
                            "header_name": c.header_name,
                        }
                        for c in rule.conditions
                    ],
                }
                for rule in waf.custom_rules
            ],
        }

    s3 = config.s3
    if s3.access_key or s3.secret_key or s3.bucket or s3.provider or s3.region:
        data["s3"] = {
            "access_key": s3.access_key,
            "secret_key": s3.secret_key,
            "bucket": s3.bucket,
            "provider": s3.provider,
            "region": s3.region,
        }

    if config.production.enabled:
        monitor = config.monitor
        data["monitor"] = {
            "system_log_path": str(monitor.system_log_path),
            "authority_file_path": str(monitor.authority_file_path),
            "system_log_max_size": monitor.system_log_max_size,
            "application_log_max_size": monitor.application_log_max_size,
        }
        if monitor.log_path:
            data["monitor"]["log_path"] = str(monitor.log_path)


BENCH_TOML_CODEC = TomlDataclassCodec(
    from_config_dict=_bench_config_from_dict,
    to_config_dict=_bench_config_to_dict,
)


def load_config(path: Path, *, validate: bool = True, strict: bool = False) -> BenchConfig:
    config = _bench_config_from_dict(Toml.loads(path.read_text(encoding="utf-8")), strict=strict)
    if validate:
        config.validate()
    return config


def dumps_config(config: BenchConfig) -> str:
    return BENCH_TOML_CODEC.dumps(config)
