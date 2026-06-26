import sys

from bench_cli.config.site_config import SiteConfig
from bench_cli.core.site import Site

from .base_task import BaseTask


class ReinstallSiteTask(BaseTask):
    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("site")
        p.add_argument("--admin-password", default="admin")
        p.add_argument("--db-type", default="mariadb", choices=["mariadb", "postgres"])
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.site = args.site
        self.admin_password = args.admin_password
        self.db_type = args.db_type

    def run(self) -> None:
        print(f"Reinstalling site '{self.site}'...")
        sys.stdout.flush()
        site = Site(SiteConfig(name=self.site, apps=[], db_type=self.db_type), self.bench)
        site.reinstall(self.admin_password)
        print(f"\nSite '{self.site}' reinstalled.")


if __name__ == "__main__":
    ReinstallSiteTask.main()
