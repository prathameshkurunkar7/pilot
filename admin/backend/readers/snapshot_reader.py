from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from pilot.integrations.s3.snapshots import OffsiteSnapshot


@dataclass
class SnapshotEntry:
    dataset: str
    tag: str
    created_at: datetime
    used_bytes: int
    is_offsite: bool = False


@dataclass
class SnapshotStatus:
    volume_enabled: bool
    snapshots_enabled: bool
    snapshots: list[SnapshotEntry] = field(default_factory=list)


class SnapshotReader:
    def __init__(self, bench_root: Path) -> None:
        self._bench_root = bench_root

    def read(self, limit: int | None = None) -> SnapshotStatus:
        """Snapshots newest first: local runs, overlaid with offsite runs from
        S3. When `limit` is given, only that many offsite runs are fetched (the
        monthly metadata files are read lazily), so a paginated caller never
        pays for a bench's full history."""
        from pilot.config.toml_store import BenchTomlStore
        from pilot.managers.volume_manager import VolumeManager
        from pilot.platform import is_linux

        self._bench_config = BenchTomlStore.for_bench(self._bench_root).read()
        volume_config = self._bench_config.volume

        if not is_linux():
            return SnapshotStatus(volume_enabled=False, snapshots_enabled=False)

        manager = VolumeManager(volume_config)
        dataset = volume_config.dataset_path
        entries = {entry.tag: entry for entry in self._read_local_snapshots(manager, dataset)}
        self._overlay_remote_snapshots(entries, dataset, limit)

        ordered = sorted(entries.values(), key=lambda entry: entry.tag, reverse=True)
        return SnapshotStatus(
            volume_enabled=True,
            snapshots_enabled=True,
            snapshots=ordered[:limit] if limit is not None else ordered,
        )

    def _read_local_snapshots(self, manager, dataset: str) -> list[SnapshotEntry]:
        return [
            SnapshotEntry(dataset=snap.dataset, tag=snap.snapshot_tag, created_at=snap.created_at, used_bytes=snap.used_bytes)
            for snap in manager.list_snapshots(dataset)
        ]

    def _overlay_remote_snapshots(self, entries: dict[str, SnapshotEntry], dataset: str, limit: int | None) -> None:
        """Marks snapshots that exist offsite and adds remote-only ones. A
        snapshot still present locally is left untouched — the local copy is
        authoritative (it has a real, known size)."""
        if not self._bench_config.s3.is_configured:
            return

        offsite_snapshot = OffsiteSnapshot.from_config(self._bench_config.s3)
        for tag in offsite_snapshot.list_snapshots(self._bench_config.name, limit=limit):
            entry = entries.setdefault(tag, SnapshotEntry(dataset=dataset, tag=tag, created_at=self._parse_tag(tag), used_bytes=0))
            entry.is_offsite = True

    def _parse_tag(self, tag: str) -> datetime:
        try:
            return datetime.strptime(tag, "%Y%m%d-%H%M%S")
        except ValueError:
            return datetime.now()
