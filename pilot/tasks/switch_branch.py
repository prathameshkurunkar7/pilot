import sys

from pilot.managers.task.base_task import BaseTask


class SwitchBranchTask(BaseTask):
    command = "switch-branch"
    required_args = ["name", "branch"]

    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("name")
        p.add_argument("branch")
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.name = args.name
        self.branch = args.branch

    def run(self) -> None:
        from pilot.exceptions import BenchError
        from pilot.managers.python_environment import PythonEnvManager

        app = self.bench.app(self.name)

        self._step("checkout", f"Switch to branch '{self.branch}'")
        try:
            app.switch_branch(self.branch)
        except BenchError as exc:
            print(str(exc))
            sys.exit(1)

        env = PythonEnvManager(self.bench)
        self._step("install", f"Reinstall {self.name}")
        env.install_app(app)
        self._step("assets", "Build assets")
        env.build_assets_for_app(app)

        self._update_bench_toml_branch()
        print(f"'{self.name}' switched to '{self.branch}' successfully.")
        self._step("done")

    def _update_bench_toml_branch(self) -> None:
        from pilot.config.toml_store import BenchTomlStore

        store = BenchTomlStore.for_bench(self.bench_root)
        with store.edit_raw() as raw:
            for app_entry in raw.get("apps", []):
                if app_entry.get("name") == self.name:
                    app_entry["branch"] = self.branch
                    break


if __name__ == "__main__":
    SwitchBranchTask.main()
