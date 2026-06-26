from bench_cli.utils import run_command
from .base_task import BaseTask


class ReinstallSiteTask(BaseTask):
    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("site")
        p.add_argument("--admin-password", default="admin")
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.site = args.site
        self.admin_password = args.admin_password

    def run(self) -> None:
        print(f"Reinstalling site '{self.site}'...")
        import sys
        sys.stdout.flush()
        cmd = [*self.bench.frappe_call, "frappe", "--site", self.site, "reinstall", "--yes",
               "--admin-password", self.admin_password]
        cmd += ["--db-type", self.bench.config.database_engine]
        if self.bench.config.database_engine != "sqlite":
            database = self.bench.config.postgres if self.bench.config.database_engine == "postgres" else self.bench.config.mariadb
            cmd += ["--db-root-username", database.admin_user]
            if database.root_password:
                cmd += ["--db-root-password", database.root_password]
        run_command(cmd, cwd=self.bench.sites_path, stream_output=True)
        print(f"\nSite '{self.site}' reinstalled.")


if __name__ == "__main__":
    ReinstallSiteTask.main()
