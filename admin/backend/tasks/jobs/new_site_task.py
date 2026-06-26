from bench_cli.commands.new_site import NewSiteCommand
from .base_task import BaseTask


class NewSiteTask(BaseTask):
    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("name")
        p.add_argument("--admin-password", default="admin")
        p.add_argument("--database-engine", choices=("mariadb", "postgres", "sqlite"))
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.name = args.name
        self.admin_password = args.admin_password
        self.database_engine = args.database_engine

    def run(self) -> None:
        NewSiteCommand(self.bench, self.name, [], self.admin_password, self.database_engine).run()


if __name__ == "__main__":
    NewSiteTask.main()
