from __future__ import annotations

from pilot.commands.base import Command


class TaskWorkerStatusCommand(Command):
    name = "status"
    help = "Show the Admin task worker state."
    group = "tasks"

    def run(self) -> None:
        from admin.backend.tasks.manager.worker_state import WorkerStore

        store = WorkerStore(self.bench.path)
        state = store.read_state()
        observed = state.status.value if state is not None else "not-started"
        print(f"Task worker: {observed} (desired: {store.read_intent().value})")
        if state is not None and state.current_task_id:
            print(f"Current task: {state.current_task_id}")
