from pilot.managers.task.base_task import BaseTask


class SetupNginxTask(BaseTask):
    command = "setup-nginx"

    def run(self) -> None:
        self._step("nginx", "Set up Nginx")
        self.bench.setup_nginx(on_progress=self._report)
        self._step("done")


if __name__ == "__main__":
    SetupNginxTask.main()
