from __future__ import annotations

import importlib
import os
import pkgutil

from pilot.managers.task.base_task import BaseTask

# This package's own machinery, not task modules — skip when scanning.
_NOT_A_TASK_MODULE = {"registry", "runner"}
_PACKAGE_DIR = os.path.dirname(__file__)


def _discover_tasks() -> list[type[BaseTask]]:
    tasks = []
    for module_info in pkgutil.iter_modules([_PACKAGE_DIR], prefix=f"{__package__}."):
        name = module_info.name.rsplit(".", 1)[-1]
        if name in _NOT_A_TASK_MODULE:
            continue
        module = importlib.import_module(module_info.name)
        for value in vars(module).values():
            if isinstance(value, type) and issubclass(value, BaseTask) and value.command:
                tasks.append(value)
    return tasks


_TASKS = _discover_tasks()
JOBS: dict[str, type[BaseTask]] = {cls.command: cls for cls in _TASKS}
WHITELIST: dict[str, list[str]] = {cls.command: cls.required_args for cls in _TASKS}
