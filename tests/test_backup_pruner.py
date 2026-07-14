from types import SimpleNamespace

from pilot.config.backup_config import BackupConfig
from pilot.core.backup_pruner import BackupPruner

_RUNS = ["20260101_020000", "20260102_020000", "20260103_020000"]  # oldest → newest


def _bench(tmp_path, scheme="fifo", keep_last=1):
    config = SimpleNamespace(backup=BackupConfig(scheme=scheme, keep_last=keep_last))
    return SimpleNamespace(sites_path=tmp_path / "sites", config=config)


def _write_local_runs(bench, site):
    backups = bench.sites_path / site / "private" / "backups"
    backups.mkdir(parents=True)
    for ts in _RUNS:
        (backups / f"{ts}-{site}-database.sql.gz").write_text("x")
    return backups


class _FakeOffsite:
    """Records deletions; raises for any run whose timestamp is in ``fail_on``."""

    def __init__(self, runs, fail_on=frozenset()):
        self._runs = runs
        self._fail_on = fail_on
        self.deleted = []

    def list_backups(self, site):
        return {ts: {"database": f"{ts}-db"} for ts in self._runs}

    def delete(self, site, timestamp, filename):
        if timestamp in self._fail_on:
            raise RuntimeError("S3 down")
        self.deleted.append((timestamp, filename))


def test_offsite_failure_keeps_local_and_is_not_reported(tmp_path) -> None:
    bench = _bench(tmp_path)
    backups = _write_local_runs(bench, "site1")
    fake = _FakeOffsite(_RUNS, fail_on={"20260102_020000"})

    pruner = BackupPruner(bench, "site1")
    pruner._offsite = lambda: fake
    pruned = pruner.prune()

    # keep_last=1 keeps only the newest run; the older two are selected for deletion.
    assert pruned == ["20260101_020000"]  # the failing run is not reported as pruned
    assert not (backups / "20260101_020000-site1-database.sql.gz").exists()
    assert (backups / "20260102_020000-site1-database.sql.gz").exists()  # kept intact on S3 error
    assert (backups / "20260103_020000-site1-database.sql.gz").exists()  # newest, never pruned


def test_prunes_local_and_offsite_when_healthy(tmp_path) -> None:
    bench = _bench(tmp_path)
    backups = _write_local_runs(bench, "site1")
    fake = _FakeOffsite(_RUNS)

    pruner = BackupPruner(bench, "site1")
    pruner._offsite = lambda: fake
    pruned = pruner.prune()

    assert sorted(pruned) == ["20260101_020000", "20260102_020000"]
    assert {ts for ts, _ in fake.deleted} == {"20260101_020000", "20260102_020000"}
    assert not (backups / "20260101_020000-site1-database.sql.gz").exists()
    assert (backups / "20260103_020000-site1-database.sql.gz").exists()
