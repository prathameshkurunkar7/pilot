from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    KILLED = "killed"


TERMINAL_TASK_STATUSES = frozenset({TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.KILLED})
ACTIVE_TASK_STATUSES = frozenset({TaskStatus.QUEUED, TaskStatus.RUNNING})

ALLOWED_TASK_TRANSITIONS = {
    TaskStatus.QUEUED: frozenset({TaskStatus.RUNNING, TaskStatus.KILLED}),
    TaskStatus.RUNNING: TERMINAL_TASK_STATUSES,
    TaskStatus.SUCCESS: frozenset(),
    TaskStatus.FAILED: frozenset(),
    TaskStatus.KILLED: frozenset(),
}


def parse_task_status(value: str) -> TaskStatus:
    try:
        return TaskStatus(value)
    except ValueError as error:
        raise ValueError(f"Unknown task status: {value!r}") from error


def validate_task_transition(current: TaskStatus, target: TaskStatus) -> None:
    if target not in ALLOWED_TASK_TRANSITIONS[current]:
        raise ValueError(f"Invalid task transition: {current.value} -> {target.value}")


FAILURE_MESSAGES = {
    "command_failed": "Task command failed.",
    "task_interrupted": "Task execution was interrupted.",
}


@dataclass(frozen=True)
class TaskFailure:
    code: str
    message: str


def safe_task_failure(value: object, status: TaskStatus) -> TaskFailure | None:
    if status != TaskStatus.FAILED:
        return None
    code = value.get("code") if isinstance(value, dict) else None
    if code not in FAILURE_MESSAGES:
        code = "command_failed"
    return TaskFailure(code=code, message=FAILURE_MESSAGES[code])


@dataclass
class TaskInfo:
    task_id: str
    command: str
    args: dict
    status: TaskStatus
    pid: int | None
    queued_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    exit_code: int | None
    output_path: Path
    queue_position: int | None = None
    failure: TaskFailure | None = None

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at is None or self.finished_at is None:
            return None
        return (self.finished_at - self.started_at).total_seconds()

    def as_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "command": self.command,
            "args": self.args,
            "status": self.status,
            "pid": self.pid,
            "queued_at": self.queued_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "queue_position": self.queue_position,
            "failure": (
                {"code": self.failure.code, "message": self.failure.message}
                if self.failure
                else None
            ),
        }
