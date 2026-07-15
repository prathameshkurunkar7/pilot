from __future__ import annotations

import stat
from pathlib import Path

import pytest

from admin.backend.tasks.manager.worker_state import (
    WorkerState,
    WorkerStatus,
    WorkerStore,
)


def test_worker_store_creates_private_worker_files(tmp_path: Path) -> None:
    store = WorkerStore(tmp_path)

    store.write_pid(4321)
    written = store.write_state(WorkerStatus.RUNNING, 4321, "task-id")

    assert store.read_pid() == 4321
    assert store.read_state() == written
    assert stat.S_IMODE(store.tasks_root.stat().st_mode) == 0o700
    for path in (store.lock_path, store.pid_path, store.state_path):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


def test_worker_pid_can_be_cleared(tmp_path: Path) -> None:
    store = WorkerStore(tmp_path)
    store.write_pid(4321)

    store.write_pid(None)

    assert store.read_pid() is None


@pytest.mark.parametrize("status", list(WorkerStatus))
def test_worker_state_round_trips_every_status(
    tmp_path: Path,
    status: WorkerStatus,
) -> None:
    store = WorkerStore(tmp_path)

    written = store.write_state(status, 1234)

    assert isinstance(written, WorkerState)
    assert store.read_state() == written


def test_missing_worker_state_returns_none(tmp_path: Path) -> None:
    store = WorkerStore(tmp_path)

    assert store.read_pid() is None
    assert store.read_state() is None


def test_unknown_worker_status_is_rejected(tmp_path: Path) -> None:
    store = WorkerStore(tmp_path)
    store.ensure_layout()
    store.state_path.write_text(
        '{"status":"lost","pid":1,"current_task_id":null,"updated_at":"2026-07-15T12:00:00+00:00"}'
    )

    with pytest.raises(ValueError, match="lost"):
        store.read_state()
