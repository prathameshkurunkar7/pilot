import argparse

from pilot.config.toml_store import BenchTomlStore
from pilot.managers.task.base_task import BaseTask


class SetupLetsEncryptTask(BaseTask):
    command = "setup-letsencrypt"

    @classmethod
    def _parser(cls) -> argparse.ArgumentParser:
        parser = super()._parser()
        parser.add_argument("--site", default="")
        parser.add_argument("--email", default="")
        return parser

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.site = args.site
        self.email = args.email

    def run(self) -> None:
        self._step("letsencrypt", "Set up Let's Encrypt")
        self._require_production_privileges()
        self._apply_email()
        self._enable_site_tls()
        self.bench.setup_letsencrypt()
        self._step("done")

    def _apply_email(self) -> None:
        if not self.email:
            return
        with BenchTomlStore.for_bench(self.bench_root).edit() as config:
            config.letsencrypt.email = self.email
        self.bench.config.letsencrypt.email = self.email

    def _enable_site_tls(self) -> None:
        if not self.site:
            return
        from pilot.core.site import Site

        Site.for_name(self.site, self.bench).set_ssl(True)


if __name__ == "__main__":
    SetupLetsEncryptTask.main()
