from __future__ import annotations

from pilot.managers.task.base_task import BaseTask
from pilot.core.backup_pruning import BackupPruner, parse_backup_timestamp
from pilot.integrations.s3.backups import OffsiteBackup
from pilot.integrations.s3.base import S3IntegrationError


class DeleteBackupTask(BaseTask):
    command = "delete-backup"
    required_args = ["site", "filenames"]

    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("site")
        p.add_argument("filenames", nargs="+")
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.site = args.site
        self.filenames = args.filenames

    def delete_from_remote(self, filename: str) -> bool:
        timestamp = parse_backup_timestamp(filename)
        if not timestamp:
            print(f"Not found (skipping): {filename}")
            return False

        try:
            offsite_backup = OffsiteBackup.from_config(self.bench.config.s3, self.bench_root)
            offsite_backup.delete(self.site, timestamp, filename)
            print(f"Deleted from S3: {filename}")
            return True
        except S3IntegrationError as e:
            print(f"Something seems wrong with s3 integration, skipping remote delete for {filename}: {e!s}")
            return False

    def run(self) -> None:
        self._step("delete", f"Delete {len(self.filenames)} backup(s) for {self.site}")
        backup_dir = BackupPruner(self.bench, self.site).backups_dir
        deleted, offsite = [], False
        for filename in self.filenames:
            path = backup_dir / filename
            if path.is_file():
                path.unlink()
                deleted.append(filename)
                print(f"Deleted: {filename}")
            elif self.bench.config.s3.is_configured and self.delete_from_remote(filename):
                deleted.append(filename)
                offsite = True

        self._record(deleted, offsite)
        self._step("done")

    def _record(self, deleted: list[str], offsite: bool) -> None:
        self._record_audit(
            "backup",
            {"site": self.site, "event": "delete", "status": "success", "files": deleted, "offsite": offsite},
        )


if __name__ == "__main__":
    DeleteBackupTask.main()
