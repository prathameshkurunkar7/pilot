from __future__ import annotations

import os
import subprocess
import sys
import threading
from pathlib import Path

from admin.backend.tasks.manager.task_queue import TaskQueue
from admin.backend.tasks.manager.task_state import TERMINAL_TASK_STATUSES
from admin.backend.tasks.manager.task_store import TaskStore
from admin.backend.tasks.manager.worker_state import WorkerStatus, WorkerStore


class TaskWorker:
    def __init__(self, bench_root: Path) -> None:
        self._bench_root = Path(bench_root)
        self._queue = TaskQueue(self._bench_root)
        self._tasks = TaskStore(self._bench_root)
        self._worker = WorkerStore(self._bench_root)
        self._wake = threading.Event()
        self._drain = threading.Event()
        self._claim_lock = threading.Lock()
        self._thread = threading.Thread(
            target=self._run,
            name="bench-task-worker",
        )

    def start(self) -> None:
        self._thread.start()

    def wake(self) -> None:
        self._wake.set()

    def request_drain(self) -> None:
        with self._claim_lock:
            self._drain.set()
        self._wake.set()

    def join(self, timeout: float | None = None) -> None:
        self._thread.join(timeout)

    def is_alive(self) -> bool:
        return self._thread.is_alive()

    def _run(self) -> None:
        lock = self._worker.try_acquire()
        if lock is None:
            return

        pid = os.getpid()
        with lock:
            self._worker.write_pid(pid)
            self._worker.write_state(WorkerStatus.STARTING, pid)
            try:
                self._work(pid)
            finally:
                self._worker.write_state(WorkerStatus.STOPPED, None)
                self._worker.write_pid(None)

    def _work(self, pid: int) -> None:
        while not self._drain.is_set():
            self._wake.clear()
            if self._run_next(pid):
                continue
            if self._drain.is_set():
                break
            self._worker.write_state(WorkerStatus.IDLE, pid)
            self._wake.wait()

    def _run_next(self, pid: int) -> bool:
        task_id = self._claim_next()
        if task_id is None:
            return False

        self._worker.write_state(WorkerStatus.RUNNING, pid, task_id)
        process = self._start_task(task_id)
        self._tasks.write_pid(task_id, process.pid)
        process.wait()
        if self._tasks.read_status(task_id) not in TERMINAL_TASK_STATUSES:
            raise RuntimeError(f"Task wrapper exited without finalizing {task_id}")
        return True

    def _claim_next(self) -> str | None:
        with self._claim_lock:
            if self._drain.is_set():
                return None
            return self._queue.claim_next()

    def _start_task(self, task_id: str) -> subprocess.Popen:
        task_dir = self._tasks.task_dir(task_id)
        kwargs = {
            "start_new_session": True,
            "stdin": subprocess.DEVNULL,
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
        }
        secret_path = task_dir / "secrets.json"
        if secret_path.exists():
            kwargs["env"] = {
                **os.environ,
                "BENCH_TASK_SECRETS_FILE": str(secret_path),
            }
        return subprocess.Popen(
            [sys.executable, "-m", "admin.backend.tasks.manager.wrapper", str(task_dir)],
            **kwargs,
        )
