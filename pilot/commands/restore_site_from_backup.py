from __future__ import annotations

import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pilot.core.bench import Bench


class NewSiteFromBackupCommand:
    def __init__(
        self,
        bench: "Bench",
        name: str,
        db_file: str,
        admin_password: str = "admin",
        public_files: str | None = None,
        private_files: str | None = None,
        db_type: str = "mariadb",
    ) -> None:
        self.bench = bench
        self.name = name
        self.db_file = db_file
        self.admin_password = admin_password
        self.public_files = public_files
        self.private_files = private_files
        self.db_type = db_type

    def run(self) -> None:
        from pilot.commands.new_site import NewSiteCommand
        from pilot.config.site_config import SiteConfig
        from pilot.core.site import Site

        # The fresh site must be created with the same engine as the backup, so the
        # restore (which reads db_type from the new site's config) lines up.
        NewSiteCommand(self.bench, self.name, [], self.admin_password, self.db_type).run()
        print(f"Restoring backup: {self.db_file}")
        sys.stdout.flush()
        site = Site(SiteConfig(name=self.name, apps=[], db_type=self.db_type), self.bench)
        site.restore(self.db_file, self.public_files, self.private_files)
