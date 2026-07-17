from __future__ import annotations

from pathlib import Path

from pilot.managers.task.runner import TaskRunner as _TaskRunner
from pilot.tasks.registry import JOBS, WHITELIST


class TaskRunner(_TaskRunner):
    """The TaskRunner bound to this app's actual task registry — what every
    caller should use. pilot.managers.task.TaskRunner is the generic engine;
    this just wires it to pilot.tasks.registry's job classes."""

    def __init__(self, bench_root: Path) -> None:
        super().__init__(bench_root, JOBS, WHITELIST)
