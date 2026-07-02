"""Offsite backup storage: uploads/downloads/deletes a bench's site backups in S3."""

from collections.abc import Iterator
from pathlib import Path

from pilot.integrations.s3.base import S3

FILE_TYPE_SUFFIXES = {
    "-database.sql.gz": "database",
    "-private-files.tar": "private_files",
    "-files.tar": "files",
    "-site_config_backup.json": "site_config",
}


def _file_type(filename: str) -> str:
    for suffix, file_type in FILE_TYPE_SUFFIXES.items():
        if filename.endswith(suffix):
            return file_type
    return "unknown"


class Metadata:
    """Tracks offsite backups for one site in monthly JSON files:
    ``sites/<site_name>/backups_metadata/<year>-<month>.json``

    Each file groups backup runs by timestamp, so a run's files
    (database, site files, private files, site config) render as one row::

        {
          "20260702_174545": {
            "database": "20260702_174545-assets_local-database.sql.gz",
            "files": "20260702_174545-assets_local-files.tar",
            "private_files": "20260702_174545-assets_local-private-files.tar",
            "site_config": "20260702_174545-assets_local-site_config_backup.json"
          }
        }
    """

    def __init__(self, s3: S3, bucket: str, site_name: str):
        self.s3 = s3
        self.bucket = bucket
        self.site_name = site_name

    def add_entry(self, date: str, timestamp: str, filename: str) -> None:
        runs = self.read_entries(date)
        runs.setdefault(timestamp, {})[_file_type(filename)] = filename
        self._write_runs(date, runs)

    def remove_entry(self, date: str, timestamp: str, filename: str) -> None:
        runs = self.read_entries(date)
        run = runs.get(timestamp)
        if run is None:
            return
        run.pop(_file_type(filename), None)
        if not run:
            runs.pop(timestamp)
        self._write_runs(date, runs)

    def read_entries(self, date: str) -> dict[str, dict[str, str]]:
        key = self._key(date)
        if not self.s3.object_exists(self.bucket, key):
            return {}
        return self.s3.read_json(self.bucket, key)

    def list_month_keys(self) -> list[str]:
        """Every monthly metadata key for this site, newest month first. Just an
        S3 listing (cheap) — doesn't fetch any file contents."""
        prefix = f"sites/{self.site_name}/backups_metadata/"
        return sorted(self.s3.list_objects(self.bucket, prefix=prefix), reverse=True)

    def iter_entries(self) -> Iterator[tuple[str, dict[str, str]]]:
        """(timestamp, files) pairs across every monthly metadata file, newest
        first. Fetches one month's file at a time — via a generator — so a
        caller that only needs the most recent runs can stop early instead of
        paying for every month's GetObject up front."""
        for key in self.list_month_keys():
            runs = self.s3.read_json(self.bucket, key)
            for timestamp in sorted(runs, reverse=True):
                yield timestamp, runs[timestamp]

    def _write_runs(self, date: str, runs: dict[str, dict[str, str]]) -> None:
        self.s3.write_json(self.bucket, self._key(date), runs)

    def _key(self, date: str) -> str:
        year, month = date[:4], date[4:6]
        return f"sites/{self.site_name}/backups_metadata/{year}-{month}.json"


class OffsiteBackup:
    """Namespaces one bench's backups under ``sites/<site_name>/backups/<date>/<time>/``
    in a bucket, so every file from one backup run groups together per site.

    Wraps a configured ``S3`` client (composition, not inheritance: this class
    is not itself an S3 client — it's a naming/orchestration layer on top of one).
    """

    def __init__(self, s3: S3, bucket: str) -> None:
        self.s3 = s3
        self.bucket = bucket

    def upload(self, site_name: str, timestamp: str, backup_path: Path, remove_local: bool = True) -> None:
        self.s3.upload_file(self.bucket, backup_path, self._remote_key(site_name, timestamp, backup_path.name))
        if remove_local:
            backup_path.unlink(missing_ok=True)

        date, _ = timestamp.split("_")
        self._metadata(site_name).add_entry(date, timestamp, backup_path.name)

    def download(self, site_name: str, timestamp: str, offsite_backup_name: str, destination: Path) -> None:
        self.s3.download_file(self.bucket, self._remote_key(site_name, timestamp, offsite_backup_name), destination)

    def delete(self, site_name: str, timestamp: str, offsite_backup_name: str) -> None:
        self.s3.delete_object(self.bucket, self._remote_key(site_name, timestamp, offsite_backup_name))

        date, _ = timestamp.split("_")
        self._metadata(site_name).remove_entry(date, timestamp, offsite_backup_name)

    def list_backups(self, site_name: str, limit: int | None = None) -> dict[str, dict[str, str]]:
        """Offsite backup runs for a site, newest first, keyed by timestamp.
        Stops reading monthly metadata files as soon as `limit` runs are
        collected, instead of fetching a site's entire backup history."""
        runs: dict[str, dict[str, str]] = {}
        for timestamp, files in self._metadata(site_name).iter_entries():
            runs[timestamp] = files
            if limit is not None and len(runs) >= limit:
                break
        return runs

    def _metadata(self, site_name: str) -> Metadata:
        return Metadata(self.s3, self.bucket, site_name)

    def _remote_key(self, site_name: str, timestamp: str, filename: str) -> str:
        date, time = timestamp.split("_")
        return f"sites/{site_name}/backups/{date}/{time}/{filename}"
