# Tasks

Tasks run long operations outside the Admin API request cycle. They are also the preferred interface for CLI commands that need progress, logs, or callbacks.

## Public API

Task classes inherit from `Task` and are exported from `pilot/tasks/__init__.py` with real imports for IDE autocomplete.

Queue tasks by class:

```python
from pilot.core.bench import Bench
from pilot.tasks import GetAndInstallAppTask

bench = Bench("main")
task_id = GetAndInstallAppTask.queue(
    bench,
    name="erpnext",
    repo="https://github.com/frappe/erpnext",
)
```

Use `queue_submission()` when the caller needs to know whether an idempotent submission created a new task.

## Task Shape

```python
from dataclasses import dataclass
from typing import ClassVar

from pilot.tasks import Task, on_failure, on_success, step


@dataclass(kw_only=True)
class ExampleTask(Task):
    command: ClassVar[str] = "example"

    site: str

    @step("run", "Running example")
    def run(self) -> None:
        self.bench.site(self.site).migrate()

    @on_success
    def refresh_site(self) -> dict:
        return {"site": self.site}

    @on_failure
    def reload_task_list(self) -> dict:
        return {}
```

`command` is the stable task name stored in task records. Constructor fields are validated before submission.

## Steps

Use `@step("key", "Label")` around meaningful phases. Step output is parsed by the task runner and exposed to the Admin UI.

Call `self.step_failed()` only when a task handles an error internally and still needs to mark the active step as failed.

## Callbacks

`@on_success`, `@on_failure`, and `@on_cancel` take no arguments. The decorated method returns callback args, and the method name becomes the operation with underscores converted to hyphens.

Return `None` to skip a callback for that task instance.

Explicit callbacks passed to `queue()` override callbacks declared on the task.

## Idempotency

Use `idempotency_key` when duplicate submissions should return the same task. Use `resource_key` when only one active task should own a resource.

Required submit-only args can be named in `required_submit_args` when the runner needs a value that is not a dataclass constructor field.

## Implementation Boundaries

- Task authoring helpers live in `pilot/tasks`.
- Execution internals live in `pilot/internal/tasks`.
- Task behavior should call core objects.
- API routes should submit tasks and return task ids.
- Commands may run tasks or call core objects directly for short work.

Do not build task command strings by hand when a task class exists.
