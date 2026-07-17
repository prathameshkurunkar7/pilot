import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from pilot.managers.task.base_task import BaseTask
from pilot.core.backup_pruning import BackupPruner
from pilot.integrations.s3.backups import OffsiteBackup
from pilot.integrations.s3.base import S3IntegrationError


class BackupSiteTask(BaseTask):
    command = "backup-site"
    required_args = ["site"]

    @classmethod
    def _parser(cls):
        p = super()._parser()
        p.add_argument("site")
        p.add_argument("--with-files", action="store_true")
        return p

    def __init__(self, bench, bench_root, args):
        super().__init__(bench, bench_root, args)
        self.site = args.site
        self.with_files = args.with_files
        self._pruner = BackupPruner(self.bench, self.site)

    def run(self) -> None:
        self._step("backup", f"Backup site {self.site}")
        # cwd matters: frappe's bench helper reads apps.txt from the current dir.
        # The task wrapper sets this, but cron invokes us directly, so set it here.
        argv = [*self.bench.frappe_call, "frappe", "--site", self.site, "backup"]
        if self.with_files:
            argv.append("--with-files")
        result = subprocess.run(argv, cwd=str(self.bench.sites_path))
        if result.returncode != 0:
            self._record(status="failed", timestamp="", files={}, offsite=False, pruned=[])
            sys.exit(result.returncode)

        timestamp, backup_files = self._pruner.latest_run()
        if not backup_files:
            print("Backup command exited 0 but produced no files.")
            self._record(status="failed", timestamp="", files={}, offsite=False, pruned=[])
            sys.exit(1)
        files = {path.name: path.stat().st_size for path in backup_files}
        offsite = self._upload(timestamp, backup_files)
        pruned = self._prune()
        self._record(status="success", timestamp=timestamp, files=files, offsite=offsite, pruned=pruned)
        self._step("done")

    def _upload(self, timestamp: str, backup_files: list[Path]) -> bool:
        if not self.bench.config.s3.is_configured:
            return False
        try:
            self._step("backup_upload", "Uploading backup to S3")
            offsite_backup = OffsiteBackup.from_config(self.bench.config.s3, self.bench_root)
            for backup_file in backup_files:
                offsite_backup.upload(self.site, timestamp, backup_file)
            return True
        except S3IntegrationError as e:
            print(f"Something seems wrong with s3 integration currently skipping remote upload: {e!s}")
            return False

    def _prune(self) -> list[str]:
        """Retention runs after every backup; a failure here must not fail the backup."""
        try:
            self._step("retention", "Applying backup retention")
            return self._pruner.prune()
        except Exception as e:
            print(f"Backup retention skipped due to error: {e!s}")
            return []

    def _record(self, status: str, timestamp: str, files: dict, offsite: bool, pruned: list[str]) -> None:
        self._record_audit(
            "backup",
            {
                "site": self.site,
                "event": "backup",
                "timestamp": timestamp,
                "finished_at": datetime.now(timezone.utc).isoformat(),
                "status": status,
                "with_files": self.with_files,
                "files": files,
                "offsite": offsite,
                "pruned": pruned,
            },
        )


if __name__ == "__main__":
    BackupSiteTask.main()
