from __future__ import annotations

import hashlib
import json
import logging
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TypedDict

from pilot.managers.task.base_task import BaseTask
from pilot.managers.task.callbacks import validate_callback
from pilot.managers.task.args import (
    fingerprint_task_args,
    public_task_args,
    reject_url_credentials,
    task_secret_args,
)
from pilot.managers.task.models import (
    TaskStatus,
)
from pilot.managers.task.process import TaskProcess
from pilot.managers.task.store import TaskStore
from pilot.managers.task.worker import task_workers
from pilot.exceptions import TaskNotRunningError

TASK_RETENTION_LIMIT = 100


def _argv_suffix(jobs: dict[str, type[BaseTask]], command: str, args: dict) -> list[str]:
    """Build a job's argv (after bench_root) from its own _parser() actions."""
    if command == "get-and-install-app" and "sites" not in args and args.get("site"):
        args = {**args, "sites": [args["site"]]}

    argv: list[str] = []
    for action in jobs[command]._parser()._actions:
        if action.dest in ("help", "bench_root") or action.dest not in args:
            continue
        value = args[action.dest]
        if not action.option_strings:
            argv += value if isinstance(value, list) else [str(value)]
        elif action.nargs == 0:
            if value:
                argv.append(action.option_strings[0])
        elif value:
            argv.append(action.option_strings[0])
            argv += value if isinstance(value, list) else [str(value)]
    return argv


class TaskCallback(TypedDict):
    operation: str
    args: dict


class TaskCallbacks(TypedDict, total=False):
    on_success: TaskCallback | None
    on_failure: TaskCallback | None
    on_cancel: TaskCallback | None


@dataclass(frozen=True)
class TaskSubmission:
    task_id: str
    created: bool


class TaskRunner:
    """Generic task-submission engine: it knows nothing about any specific
    task. Callers supply the command -> job class registry and the
    command -> required-args whitelist; see pilot.tasks.runner.TaskRunner
    for the bound instance used across the app."""

    def __init__(
        self,
        bench_root: Path,
        jobs: dict[str, type[BaseTask]],
        whitelist: dict[str, list[str]],
    ) -> None:
        self._bench_root = bench_root
        self._jobs = jobs
        self._whitelist = whitelist
        self._store = TaskStore(bench_root)
        self._processes = TaskProcess(bench_root)

    def run(
        self,
        command: str,
        args: dict,
        callbacks: TaskCallbacks | None = None,
        idempotency_key: str | None = None,
        resource_key: str | None = None,
    ) -> str:
        return self.submit(
            command,
            args,
            callbacks=callbacks,
            idempotency_key=idempotency_key,
            resource_key=resource_key,
        ).task_id

    def submit(
        self,
        command: str,
        args: dict,
        callbacks: TaskCallbacks | None = None,
        idempotency_key: str | None = None,
        resource_key: str | None = None,
    ) -> TaskSubmission:
        callback_payload = {}
        for trigger, spec in (callbacks or {}).items():
            if trigger not in ("on_success", "on_failure", "on_cancel"):
                raise ValueError(f"Unknown callback trigger: {trigger!r}")
            if spec is not None:
                callback_payload[trigger] = validate_callback(spec)
        task_id = self._generate_task_id()
        command_argv = self._build_argv(command, args)
        secret_args = task_secret_args(command, args)

        queued_at = datetime.now(timezone.utc).isoformat()
        meta = {
            "task_id": task_id,
            "command": command,
            "args": public_task_args(command, args),
            "command_argv": command_argv,
            "queued_at": queued_at,
            "started_at": None,
            "finished_at": None,
            "exit_code": None,
            "failure": None,
            "bench_root": str(self._bench_root),
        }
        private_files = {}
        if secret_args:
            private_files["secrets.json"] = json.dumps(secret_args)
        if callback_payload:
            private_files["callbacks.json"] = json.dumps(callback_payload, indent=2)
        if idempotency_key is None:
            self._store.create_queued(
                meta,
                private_files,
                resource_key=resource_key,
            )
            submission = TaskSubmission(task_id, True)
        else:
            idempotency_digest = self._idempotency_digest(idempotency_key)
            request_fingerprint = self._request_fingerprint(command, args)
            creation = self._store.create_idempotent_queued(
                meta,
                private_files,
                idempotency_digest,
                request_fingerprint,
                resource_key=resource_key,
            )
            if not creation.created:
                return TaskSubmission(creation.task_id, False)
            submission = TaskSubmission(creation.task_id, True)
        self._run_post_submission_housekeeping()
        return submission

    def _run_post_submission_housekeeping(self) -> None:
        for operation in (
            lambda: task_workers.wake(self._bench_root),
            lambda: self._store.purge_terminal(TASK_RETENTION_LIMIT),
        ):
            try:
                operation()
            except Exception as exc:
                logging.debug("Post-submission housekeeping step failed: %s", exc)

    def kill(self, task_id: str) -> None:
        status = self._store.read_status(task_id)
        if status not in {TaskStatus.QUEUED, TaskStatus.RUNNING}:
            raise TaskNotRunningError(
                f"Task is not active: {task_id} (status={status.value})"
            )

        if status == TaskStatus.QUEUED:
            if not self._store.transition(
                task_id,
                TaskStatus.QUEUED,
                TaskStatus.KILLED,
                {"finished_at": datetime.now(timezone.utc).isoformat()},
            ):
                current = self._store.read_status(task_id)
                raise TaskNotRunningError(
                    f"Task is not active: {task_id} (status={current.value})"
                )
            self._store.remove_private_files(task_id, "secrets.json")
            try:
                task_workers.wake(self._bench_root)
            except Exception as exc:
                logging.debug("Failed to wake task workers after kill: %s", exc)
            return
        self._processes.cancel(task_id)

    def _build_argv(self, command: str, args: dict) -> list[str]:
        if command not in self._whitelist:
            raise ValueError(f"Unknown command: {command!r}. Allowed: {sorted(self._whitelist)}")
        reject_url_credentials(args)

        required = self._whitelist[command]
        for key in required:
            if key not in args:
                raise ValueError(f"Command {command!r} requires arg {key!r}")
        if "admin_password" in required:
            password = args["admin_password"]
            if not isinstance(password, str) or not password.strip():
                raise ValueError("admin_password must not be empty")

        module = self._jobs[command].__module__
        return [
            sys.executable, "-m", module, str(self._bench_root),
            *_argv_suffix(self._jobs, command, args),
        ]

    @staticmethod
    def _generate_task_id() -> str:
        return datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(3)

    @staticmethod
    def _idempotency_digest(key: str) -> str:
        if not isinstance(key, str) or not key or len(key) > 255:
            raise ValueError("Idempotency-Key must contain between 1 and 255 characters")
        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def _request_fingerprint(command: str, args: dict) -> str:
        request = json.dumps(
            {"command": command, "args": fingerprint_task_args(command, args)},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(request.encode()).hexdigest()
