import sys

from pilot.managers.task.base_task import BaseTask


class InstallAppTask(BaseTask):
    command = "install-app"
    required_args = ["site", "app"]

    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("site")
        p.add_argument("app")
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.site = args.site
        self.app = args.app

    def run(self) -> None:
        from pilot.core.site import Site
        from pilot.exceptions import BenchError
        from pilot.managers.python_environment import PythonEnvManager

        app = self.bench.app(self.app)
        site = Site.for_name(self.site, self.bench)

        self._step("install", f"Install {self.app} into {self.site}")
        try:
            dependencies = site.install_app_with_dependencies(app)
        except BenchError as exc:
            print(str(exc), file=sys.stderr)
            sys.exit(1)

        env = PythonEnvManager(self.bench)
        for dependency_app in [app, *dependencies]:
            self._step(f"assets_{dependency_app.config.name}", f"Build assets for {dependency_app.config.name}")
            env.build_assets_for_app(dependency_app)

        self._step("done")


if __name__ == "__main__":
    InstallAppTask.main()
