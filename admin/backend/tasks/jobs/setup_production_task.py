from bench_cli.commands.setup.production import SetupProductionCommand
from .base_task import BaseTask


class SetupProductionTask(BaseTask):
    def run(self) -> None:
        SetupProductionCommand(self.bench).run()


if __name__ == "__main__":
    SetupProductionTask.main()
