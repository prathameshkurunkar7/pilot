from __future__ import annotations

from typing import TypedDict


class TaskCallback(TypedDict):
    operation: str
    args: dict


class TaskCallbacks(TypedDict, total=False):
    on_success: TaskCallback | None
    on_failure: TaskCallback | None
    on_cancel: TaskCallback | None


def on_success(func):
    return _callback_decorator("on_success", func)


def on_failure(func):
    return _callback_decorator("on_failure", func)


def on_cancel(func):
    return _callback_decorator("on_cancel", func)


def task_callbacks_for(task) -> TaskCallbacks:
    callbacks: TaskCallbacks = {}
    for method_name in dir(task):
        method = getattr(task, method_name)
        specs = getattr(method, "_task_callbacks", ())
        for trigger, operation in specs:
            args = method()
            if args is None:
                continue
            if trigger in callbacks:
                raise ValueError(
                    f"Multiple {trigger} callbacks declared for {type(task).__name__}."
                )
            callbacks[trigger] = {"operation": operation, "args": args}
    return callbacks


def _callback_decorator(trigger: str, func):
    callbacks = list(getattr(func, "_task_callbacks", ()))
    callbacks.append((trigger, func.__name__.replace("_", "-")))
    func._task_callbacks = tuple(callbacks)
    return func
