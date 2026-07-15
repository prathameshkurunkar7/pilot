from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from admin.backend.tasks.manager.process_identity import (
    ProcessIdentity,
    ProcessInspector,
    ProcessOwnership,
)
from admin.backend.tasks.manager.task_state import TaskStatus
from admin.backend.tasks.manager.task_store import TaskStore
from pilot.exceptions import TaskNotFoundError

_READY_FD_ENV = "BENCH_TASK_READY_FD"
_LAUNCH_ID_ENV = "BENCH_TASK_LAUNCH_ID"


class TaskProcessStartError(RuntimeError):
    pass


@dataclass(frozen=True)
class TaskProcessRecord:
    task_id: str
    argv: list[str]
    identity: ProcessIdentity

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "argv": self.argv,
            "identity": self.identity.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> TaskProcessRecord:
        return cls(
            task_id=str(data["task_id"]),
            argv=[str(value) for value in data["argv"]],
            identity=ProcessIdentity.from_dict(data["identity"]),
        )


class TaskProcess:
    def __init__(self, bench_root: Path) -> None:
        self._store = TaskStore(bench_root)
        self._inspector = ProcessInspector()

    def start(self, task_id: str) -> subprocess.Popen:
        task_dir = self._store.task_dir(task_id)
        argv = [
            sys.executable,
            "-m",
            "admin.backend.tasks.manager.wrapper",
            str(task_dir),
        ]
        launch_id = secrets.token_hex(16)
        read_fd, write_fd = os.pipe()
        process = None
        try:
            process = subprocess.Popen(
                argv,
                start_new_session=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=self._environment(task_dir, launch_id, read_fd),
                pass_fds=(read_fd,),
            )
            os.close(read_fd)
            read_fd = -1
            identity = self._inspector.capture(process.pid, argv, launch_id)
            record = TaskProcessRecord(task_id, argv, identity)
            self._store.write_process(task_id, process.pid, record.to_dict())
            os.write(write_fd, b"1")
            return process
        except Exception as error:
            self._abort_start(task_id, process)
            raise TaskProcessStartError(f"Could not start task {task_id}") from error
        finally:
            if read_fd >= 0:
                os.close(read_fd)
            os.close(write_fd)

    def read(self, task_id: str) -> TaskProcessRecord | None:
        data = self._store.read_process(task_id)
        return TaskProcessRecord.from_dict(data) if data is not None else None

    def ownership(self, task_id: str) -> ProcessOwnership:
        try:
            record = self.read(task_id)
            if record is None or record.task_id != task_id:
                return ProcessOwnership.UNKNOWN
            return self._inspector.inspect(record.identity, record.argv)
        except (KeyError, TypeError, ValueError, OSError, json.JSONDecodeError):
            return ProcessOwnership.UNKNOWN

    def reconcile(self) -> str | None:
        for task_id in self._store.task_ids_with_process():
            ownership = self.ownership(task_id)
            if ownership in {ProcessOwnership.OWNED, ProcessOwnership.UNKNOWN}:
                return task_id
            try:
                status = self._store.read_status(task_id)
            except (OSError, ValueError, TaskNotFoundError):
                return task_id
            if status == TaskStatus.RUNNING:
                self._interrupt(task_id)
            elif status != TaskStatus.QUEUED:
                self._store.remove_private_files(task_id, "process.json")
            else:
                return task_id
        return None

    def _environment(self, task_dir: Path, launch_id: str, read_fd: int) -> dict[str, str]:
        environment = {
            **os.environ,
            _READY_FD_ENV: str(read_fd),
            _LAUNCH_ID_ENV: launch_id,
        }
        secret_path = task_dir / "secrets.json"
        if secret_path.exists():
            environment["BENCH_TASK_SECRETS_FILE"] = str(secret_path)
        return environment

    def _abort_start(
        self,
        task_id: str,
        process: subprocess.Popen | None,
    ) -> None:
        if process is not None:
            try:
                process.kill()
            except OSError:
                pass
            process.wait()
        self._store.remove_private_files(task_id, "process.json", "pid")
        self._interrupt(task_id)

    def _interrupt(self, task_id: str) -> None:
        self._store.transition(
            task_id,
            TaskStatus.RUNNING,
            TaskStatus.FAILED,
            {
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "failure": {"code": "task_interrupted"},
            },
        )
        self._store.remove_private_files(
            task_id,
            "process.json",
            "secrets.json",
            "callbacks.json",
        )
