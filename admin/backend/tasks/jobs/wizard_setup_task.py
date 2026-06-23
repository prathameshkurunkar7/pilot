from __future__ import annotations

from bench_cli.commands.init import InitCommand
from bench_cli.commands.setup.production import SetupProductionCommand

from .base_task import BaseTask


class WizardSetupTask(BaseTask):
    """The whole wizard as a single task: initialize the bench, then deploy it to
    production when the user chose a process manager during setup.

    Running both in one task gives the frontend one continuous stream to follow
    and one state to resume — no stitching two tasks (and two SSE connections)
    together, and no in-between window where the bench looks initialized but the
    deploy hasn't started. The production deploy is just another step in the same
    output, prefixed with an `[N/M]` marker so the wizard names it like the rest.
    """

    def run(self) -> None:
        InitCommand(self.bench).run()
        if self.bench.config.production.process_manager:
            print("[1/1] Deploying to production", flush=True)
            SetupProductionCommand(self.bench).run()


if __name__ == "__main__":
    WizardSetupTask.main()
