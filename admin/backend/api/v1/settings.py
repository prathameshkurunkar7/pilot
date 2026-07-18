from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from admin.backend.api.responses import error_response
from admin.backend.middleware import client_ip

from admin.backend.api.v1.settings_apply import _SettingsApplyFailed, _apply_post_save_changes
from admin.backend.api.v1.settings_config import ConfigPatcher
from admin.backend.api.v1.settings_payload import (
    _build_settings_response,
    _firewall_payload,
    _restart_trigger_values,
    _s3_payload,
    _waf_payload,
)
from pilot.config import BenchTomlStore
from pilot.core.bench import Bench

settings_bp = Blueprint("settings", __name__)
audit_bp = Blueprint("audit", __name__)
network_bp = Blueprint("network", __name__)


class _SettingsUpdateRejected(Exception):
    pass


@settings_bp.get("")
def get_settings():
    bench_root = Path(current_app.config["BENCH_ROOT"])
    try:
        config = BenchTomlStore.for_bench(bench_root).read()
    except Exception:
        return error_response("settings_unavailable", "Could not read settings.", 500)
    return jsonify(_build_settings_response(config))


_AUDIT_LOG_DEFAULT_LIMIT = 50
_AUDIT_LOG_MAX_LIMIT = 500


@audit_bp.get("/audit-events")
def audit_log():
    """The bench-wide audit log as JSON, newest first. The log has no dedicated
    UI — it's viewed directly, paginated with ``limit``/``cursor`` query params,
    and optionally filtered by ``type``/``status``/``site``."""
    from admin.backend.api.responses import paginated_response, parse_pagination
    from pilot.core.audit_log import AuditLog

    bench_root = Path(current_app.config["BENCH_ROOT"])
    limit, offset = parse_pagination(_AUDIT_LOG_DEFAULT_LIMIT, _AUDIT_LOG_MAX_LIMIT)
    try:
        log = AuditLog(Bench(BenchTomlStore.for_bench(bench_root).read(), bench_root))

        def fetch_newest(count: int) -> list:
            return log.entries(
                entry_type=request.args.get("type") or None,
                site=request.args.get("site") or None,
                status=request.args.get("status") or None,
                limit=count,
            )

        return paginated_response(fetch_newest, limit, offset)
    except Exception:
        return error_response("audit_unavailable", "Could not read audit events.", 500)


@network_bp.get("/network/client")
def my_ip():
    """The requesting client's IP, so the UI can tell the operator which address to
    allow-list before blocking by default. Forwarded addresses are accepted only
    from the configured local nginx peer."""
    return jsonify({"ip": client_ip(default="")})


@settings_bp.patch("")
def update_settings():
    bench_root = Path(current_app.config["BENCH_ROOT"])
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("malformed_request", "Expected a JSON object.", 400)
    store = BenchTomlStore.for_bench(bench_root)
    try:
        with store.edit() as config:
            old_restart = _restart_trigger_values(config)
            old_firewall = _firewall_payload(config)
            old_waf = _waf_payload(config)
            old_s3_config = _s3_payload(config)

            if error := ConfigPatcher(config, data).apply():
                raise _SettingsUpdateRejected(error)

            # Verify the bucket before persisting while the config transaction
            # is still locked, so the validated value is exactly what commits.
            if _s3_payload(config) != old_s3_config and config.s3.access_key:
                from pilot.integrations.s3.base import S3, S3IntegrationError

                try:
                    S3.from_config(config.s3)
                except S3IntegrationError as error:
                    raise _SettingsUpdateRejected(str(error)) from error
    except _SettingsUpdateRejected as error:
        return error_response("invalid_settings", str(error), 422)
    except Exception:
        return error_response("settings_update_failed", "Could not update settings.", 500)

    try:
        restarted, waf_warning = _apply_post_save_changes(
            bench_root,
            config,
            old_restart,
            old_firewall,
            old_waf,
            old_s3_config,
        )
    except _SettingsApplyFailed as error:
        return error_response(error.code, error.message, 500, {"saved": True})

    result = {"restarted": restarted}
    if waf_warning:
        result["waf_warning"] = waf_warning
    return jsonify(result)
