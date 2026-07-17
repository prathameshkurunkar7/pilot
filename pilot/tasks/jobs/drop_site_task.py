from pilot.config.site import SiteConfig
from pilot.core.site import Site
from pilot.tasks.jobs.base_task import BaseTask


class DropSiteTask(BaseTask):
    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("name")
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.name = args.name

    def run(self) -> None:
        self._require_production_privileges()
        self._step("drop", f"Drop site {self.name}")
        Site(SiteConfig(name=self.name, apps=[]), self.bench).drop(on_progress=self._report)
        self._step("done")


if __name__ == "__main__":
    DropSiteTask.main()
