from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, g, jsonify, request

from admin.backend.api.responses import accepted_task_response, error_response, no_content_response
from admin.backend.api.v1.setup_config import read_defaults as _read_defaults
from admin.backend.api.v1.setup_config import validate_configuration as _validate
from admin.backend.api.v1.setup_database import database_validation, database_validation_state
from admin.backend.api.v1.setup_state import (
    clear_wizard_marker_if_idle as _clear_wizard_marker_if_idle,
)
from admin.backend.api.v1.setup_state import running_setup_task as _running_setup_task
from admin.backend.api.v1.setup_state import setup_handoff_task as _setup_handoff_task
from admin.backend.api.v1.setup_state import wizard_marker_path
from admin.backend.middleware import allow_during_setup, set_session_cookie
from pilot.config.bench_toml_builder import (
    FRAMEWORK_BRANCHES,
    current_port_offset,
)
from pilot.config import BenchTomlStore
from pilot.exceptions import TaskConflictError, TaskNotFoundError
from pilot.internal.atomic_file import exclusive_file_lock, replace_private_text_locked
from pilot.managers.task import TaskReader, TaskStatus
from pilot.tasks import TaskRunner

setup_bp = Blueprint("setup", __name__)


@setup_bp.get("/configuration")
@allow_during_setup
def get_configuration():
    bench_root = Path(current_app.config["BENCH_ROOT"])
    return jsonify(_read_defaults(bench_root))


@setup_bp.get("/framework-branches")
@allow_during_setup
def get_framework_branches():
    return jsonify({"branches": FRAMEWORK_BRANCHES})


@setup_bp.put("/configuration")
@allow_during_setup
def update_configuration():
    bench_root = Path(current_app.config["BENCH_ROOT"])
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("malformed_request", "Expected a JSON object.", 400)

    with exclusive_file_lock(bench_root / ".setup-configuration"):
        return _update_configuration(bench_root, data)


def _update_configuration(bench_root: Path, data: dict):
    store = BenchTomlStore.for_bench(bench_root)
    current = {}
    if store.exists():
        try:
            current = store.read_flat()
        except Exception:
            return error_response(
                "configuration_unavailable",
                "Setup configuration is unavailable.",
                503,
            )
    if current.get("admin_password") and g.jwt_claims is None:
        return error_response(
            "authentication_required",
            "Authentication is required.",
            401,
        )

    settings = {**current, **data, "admin_enabled": True}
    error = _validate(settings)
    if error:
        return error_response("invalid_setup_configuration", error, 422)

    toml_path = bench_root / "bench.toml"
    try:
        store.write_flat(
            current.get("bench_name") or bench_root.name,
            {**data, "admin_enabled": True},
            port_offset=current_port_offset(toml_path),
        )
    except (TypeError, ValueError):
        return error_response(
            "invalid_setup_configuration",
            "Setup configuration contains invalid fields.",
            422,
        )
    except Exception:
        return error_response(
            "configuration_update_failed",
            "Could not update setup configuration.",
            500,
        )

    resp = jsonify(_read_defaults(bench_root))
    if settings.get("admin_password"):
        _issue_setup_session(resp, toml_path)
    return resp


def _issue_setup_session(resp, toml_path: Path) -> None:
    from admin.backend.auth import ensure_jwt_secret, issue_token

    set_session_cookie(
        resp,
        issue_token(ensure_jwt_secret(toml_path)),
        current_app.config["SESSION_COOKIE_SECURE"],
    )


@setup_bp.post("/database-validations")
@allow_during_setup
def validate_database():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("malformed_request", "Expected a JSON object.", 400)
    try:
        engine, manager, password, existing = database_validation(
            bench_root=Path(current_app.config["BENCH_ROOT"]),
            data=data,
        )
        state = database_validation_state(manager, password, existing)
    except ValueError as error:
        return error_response(
            "invalid_database_configuration",
            str(error),
            422,
        )
    except Exception:
        return error_response(
            "database_validation_failed",
            "Could not validate the database configuration.",
            500,
        )
    return jsonify({"engine": engine, "state": state})


@setup_bp.post("/actions/start")
@allow_during_setup
def start_setup():
    bench_root = Path(current_app.config["BENCH_ROOT"])
    idempotency_key = request.headers.get("Idempotency-Key")
    if not idempotency_key:
        return error_response(
            "idempotency_key_required",
            "Idempotency-Key is required.",
            422,
        )
    try:
        config = BenchTomlStore.for_bench(bench_root).read()
        config.validate()
    except Exception:
        return error_response(
            "invalid_setup_configuration",
            "Setup configuration is invalid.",
            422,
        )

    marker = wizard_marker_path(bench_root)
    try:
        with exclusive_file_lock(marker):
            existing = _setup_handoff_task(bench_root)
            if existing:
                replace_private_text_locked(marker, existing.task_id)
                return accepted_task_response(bench_root, existing.task_id)
            replace_private_text_locked(marker, "")
            task_id = TaskRunner(bench_root).run(
                "wizard-setup",
                {},
                idempotency_key=idempotency_key,
            )
            replace_private_text_locked(marker, task_id)
            return accepted_task_response(bench_root, task_id)
    except TaskConflictError as error:
        _clear_wizard_marker_if_idle(bench_root)
        return error_response("task_conflict", str(error), 409)
    except ValueError as error:
        _clear_wizard_marker_if_idle(bench_root)
        return error_response("invalid_setup_task", str(error), 422)
    except Exception:
        _clear_wizard_marker_if_idle(bench_root)
        return error_response("setup_start_failed", "Could not start setup.", 500)


@setup_bp.post("/actions/finish")
@allow_during_setup
def finish_setup():
    import os
    import signal
    import threading

    bench_root = Path(current_app.config["BENCH_ROOT"])
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return error_response("malformed_request", "Expected a JSON object.", 400)
    task_id = data.get("task_id")
    if not isinstance(task_id, str) or not task_id:
        return error_response("invalid_task", "task_id is required.", 422)

    try:
        task = TaskReader(bench_root).read_task(task_id)
    except TaskNotFoundError as error:
        return error_response("task_not_found", str(error), 404)
    except Exception:
        return error_response("task_unavailable", "Could not read setup task.", 500)

    if task.command != "wizard-setup":
        return error_response("setup_task_required", "Task is not a setup task.", 409)
    if task.status != TaskStatus.SUCCESS:
        return error_response(
            "setup_not_complete",
            "Setup task has not completed successfully.",
            409,
        )
    marker = wizard_marker_path(bench_root)
    with exclusive_file_lock(marker):
        handoff = _setup_handoff_task(bench_root)
        if handoff is None or handoff.task_id != task_id:
            return error_response(
                "setup_task_mismatch",
                "Task is not the current setup attempt.",
                409,
            )
        if _running_setup_task(bench_root):
            return error_response(
                "setup_active",
                "Another setup task is still active.",
                409,
            )
        if not (bench_root / "config" / "Procfile").exists():
            return error_response(
                "setup_not_initialized",
                "Bench setup has not finished.",
                409,
            )
        marker.unlink(missing_ok=True)
    response = no_content_response()
    if current_app.config.get("WIZARD_SERVER"):
        response.call_on_close(
            lambda: threading.Timer(
                0.1,
                lambda: os.kill(os.getpid(), signal.SIGTERM),
            ).start()
        )
    return response
