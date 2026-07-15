from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from flask import Flask

from admin.backend.views.tasks import tasks_bp
from admin.backend.tasks.manager.task_state import TaskStatus
from admin.backend.tasks.manager.task_store import TaskStore
from pilot.exceptions import TaskConflictError


def client(bench_root: Path):
    app = Flask(__name__)
    app.config["BENCH_ROOT"] = bench_root
    app.register_blueprint(tasks_bp, url_prefix="/api/tasks")
    return app.test_client()


def test_run_forwards_idempotency_key(tmp_path: Path) -> None:
    with patch(
        "admin.backend.views.tasks.TaskRunner.run",
        return_value="20260715-120000-aabbcc",
    ) as run:
        response = client(tmp_path).post(
            "/api/tasks/run",
            json={"command": "build", "app": "frappe"},
            headers={"Idempotency-Key": "client-request-key"},
        )

    assert response.status_code == 200
    run.assert_called_once_with(
        "build",
        {"app": "frappe"},
        idempotency_key="client-request-key",
    )


def test_run_returns_conflict_for_incompatible_idempotency_key(tmp_path: Path) -> None:
    with patch(
        "admin.backend.views.tasks.TaskRunner.run",
        side_effect=TaskConflictError("Idempotency key conflict"),
    ):
        response = client(tmp_path).post(
            "/api/tasks/run",
            json={"command": "build"},
            headers={"Idempotency-Key": "client-request-key"},
        )

    assert response.status_code == 409
    assert response.get_json() == {
        "ok": False,
        "error": "Idempotency key conflict",
    }


def test_task_detail_exposes_queue_position_and_safe_failure(tmp_path: Path) -> None:
    task_id = "20260715-120000-aabbcc"
    store = TaskStore(tmp_path)
    store.create_queued(
        {
            "task_id": task_id,
            "command": "build",
            "args": {},
            "queued_at": "2026-07-15T12:00:00+00:00",
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "failure": None,
        }
    )

    queued = client(tmp_path).get(f"/api/tasks/{task_id}").get_json()["task"]
    store.transition(
        task_id,
        TaskStatus.QUEUED,
        TaskStatus.RUNNING,
        {"started_at": "2026-07-15T12:00:01+00:00"},
    )
    store.transition(
        task_id,
        TaskStatus.RUNNING,
        TaskStatus.FAILED,
        {
            "finished_at": "2026-07-15T12:00:02+00:00",
            "exit_code": 1,
            "failure": {"code": "unknown", "message": "secret text"},
        },
    )
    failed = client(tmp_path).get(f"/api/tasks/{task_id}").get_json()["task"]

    assert queued["queue_position"] == 1
    assert queued["failure"] is None
    assert failed["queue_position"] is None
    assert failed["failure"] == {
        "code": "command_failed",
        "message": "Task command failed.",
    }
    assert "secret text" not in str(failed)
