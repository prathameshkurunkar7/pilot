from __future__ import annotations

import typing
from pathlib import Path

if typing.TYPE_CHECKING:
    from pilot.core.bench import Bench
    from pilot.managers.mariadb_manager import MariaDBManager
    from pilot.managers.volume_manager import VolumeManager


class SnapshotOrchestrator:
    """Snapshot/rollback the bench's single dataset (files + database).

    Because the database lives on the same dataset, every snapshot quiesces
    MariaDB (FLUSH TABLES WITH READ LOCK) for a consistent on-disk state, and
    every rollback stops MariaDB and puts sites into maintenance mode."""

    def __init__(
        self,
        volume: VolumeManager,
        mariadb: MariaDBManager | None = None,
        bench: Bench | None = None,
    ) -> None:
        self._volume = volume
        self._mariadb = mariadb
        self._bench = bench

    @property
    def _dataset(self) -> str:
        return self._volume.config.dataset_path

    def create_snapshot(self, tag: str) -> None:
        if self._mariadb:
            with self._mariadb.snapshot_lock():
                self._volume.snapshot(self._dataset, tag)
        else:
            self._volume.snapshot(self._dataset, tag)

    def rollback_snapshot(self, tag: str) -> None:
        if self._bench:
            self._bench.set_maintenance_mode(True)
        try:
            if self._mariadb:
                self._mariadb.stop()
            try:
                self._volume.rollback_snapshot(self._dataset, tag)
            finally:
                if self._mariadb:
                    self._mariadb.start()
        finally:
            if self._bench:
                self._bench.set_maintenance_mode(False)

    def restore_downloaded_snapshot(self, tag: str) -> None:
        """Promotes a snapshot downloaded into `<dataset>-restored-<tag>`
        (see `OffsiteSnapshot.download`) to become the bench's live dataset.

        `zfs rollback` can't do this — it only replays a dataset's own
        snapshot history, and a download lives on a separate filesystem — so
        this is a rename swap instead: the current live dataset is kept,
        renamed aside (not destroyed), and the restored one takes its place.
        """
        from pilot.managers.volume_manager import VolumeError

        if not self._bench or not self._mariadb:
            raise VolumeError("Restoring a downloaded snapshot needs both a bench and a MariaDB manager.")

        restored = f"{self._dataset}-restored-{tag}"
        if not self._volume.dataset_exists(restored):
            raise VolumeError(f"No downloaded snapshot found for '{tag}'. Download it first.")

        self._ensure_bench_stopped()
        self._bench.set_maintenance_mode(True)
        try:
            self._mariadb.stop()
            try:
                self._swap_dataset(restored, tag)
            finally:
                self._mariadb.start()
        finally:
            self._bench.set_maintenance_mode(False)

    def _ensure_bench_stopped(self) -> None:
        """The swap unmounts the bench path; running workers hold files open
        on it, which makes the unmount fail and the old dataset undeletable."""
        from pilot.managers.volume_manager import VolumeError
        from pilot.managers.process_manager import ProcessManager

        if ProcessManager.detect_running(self._bench).is_running():
            raise VolumeError(
                "The bench must be stopped before restoring a downloaded snapshot.\n"
                "Run `bench stop`, then retry, and `bench start` afterwards."
            )

    def _swap_dataset(self, restored: str, tag: str) -> None:
        from datetime import datetime

        live = self._dataset
        mariadb_datadir = Path(self._mariadb.data_dir())
        bench_path = self._bench.path

        # Bind mounts go stale once the dataset under them is renamed, so
        # drop them first. The bench is stopped, so these can't be busy.
        self._volume.unmount(bench_path)
        self._volume.unmount(mariadb_datadir)

        aside = f"{live}-before-restore-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

        live_mount = self._volume.get_mountpoint(live)
        self._volume.rename_dataset(live, aside)

        try:
            self._volume.clear_mountpoint(aside)
            self._volume.rename_dataset(restored, live)
            self._volume.set_mountpoint(live, live_mount)

            mount = self._volume.get_mountpoint(live)
            self._volume.bind_mount(mount / "benches", bench_path)
            self._volume.bind_mount(mount / "mariadb", mariadb_datadir)
        except Exception:
            # `live` no longer exists past this point until we put `aside`
            # back — without this, the caller's mariadb.start() would run
            # against a dataset that isn't there.
            self._restore_original_dataset(aside, live, live_mount, bench_path, mariadb_datadir)
            raise

        self._volume.destroy_dataset(aside)
        self._volume.destroy_snapshot(live, tag)

    def _restore_original_dataset(
        self, aside: str, live: str, live_mount: Path, bench_path: Path, mariadb_datadir: Path
    ) -> None:
        """Best-effort rollback of a failed swap: put the original dataset
        back under its live name and mount, so the bench isn't left with no
        live dataset at all."""
        self._volume.rename_dataset(aside, live)
        self._volume.set_mountpoint(live, live_mount)
        mount = self._volume.get_mountpoint(live)
        self._volume.bind_mount(mount / "benches", bench_path)
        self._volume.bind_mount(mount / "mariadb", mariadb_datadir)


def get_orchestrator(bench_root):
    from pilot.config.toml_store import BenchTomlStore
    from pilot.core.bench import Bench
    from pilot.managers.mariadb_manager import MariaDBManager
    from pilot.managers.volume_manager import VolumeManager

    bench_config = BenchTomlStore.for_bench(bench_root).read()
    volume = VolumeManager(bench_config.volume)
    mariadb = MariaDBManager(bench_config.mariadb)
    bench = Bench(bench_config, bench_root)
    return SnapshotOrchestrator(volume, mariadb, bench)
