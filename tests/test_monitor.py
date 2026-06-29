import json
from pathlib import Path
from unittest.mock import patch

from pilot.config.bench_config import BenchConfig
from pilot.config.mariadb_config import MariaDBConfig
from pilot.config.production_config import ProductionConfig
from pilot.config.redis_config import RedisConfig
from pilot.config.worker_config import WorkerConfig
from pilot.core.bench import Bench
from pilot.core.monitor import Monitor


def _make_bench(path: Path, name: str = "my-bench") -> Bench:
    config = BenchConfig(
        name=name,
        python_version="3.14",
        mariadb=MariaDBConfig(),
        redis=RedisConfig(),
        workers=WorkerConfig(),
    )
    return Bench(config, path)


def _make_monitor(bench: Bench, authority_file: Path) -> Monitor:
    with patch.object(Monitor, "setup"):
        monitor = Monitor(bench)
    monitor.bench.config.monitor.authority_file_path = authority_file
    monitor.bench.config.monitor.log_path = bench.path / f"{bench.config.name}-stats.log"
    return monitor


def _sibling(name: str, process_manager: str = "") -> tuple[Path, BenchConfig]:
    config = BenchConfig(
        name=name,
        python_version="3.14",
        mariadb=MariaDBConfig(),
        redis=RedisConfig(),
        workers=WorkerConfig(),
        production=ProductionConfig(enabled=bool(process_manager), process_manager=process_manager),
    )
    return Path(f"/fake/{name}"), config


# ── is_system_log_authority ──────────────────────────────────────────────────


def test_authority_claimed_when_no_file_exists(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)

    assert monitor.is_system_log_authority is True
    assert authority_file.read_text() == "my-bench"


def test_authority_true_when_already_recorded(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    authority_file.write_text("my-bench")
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)

    assert monitor.is_system_log_authority is True


def test_authority_false_when_sibling_runs_systemd(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    authority_file.write_text("other-bench")
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)

    with patch("pilot.core.monitor.iter_sibling_benches", return_value=iter([_sibling("other-bench", "systemd")])):
        assert monitor.is_system_log_authority is False


def test_authority_false_when_sibling_runs_supervisor(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    authority_file.write_text("other-bench")
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)

    with patch("pilot.core.monitor.iter_sibling_benches", return_value=iter([_sibling("other-bench", "supervisor")])):
        assert monitor.is_system_log_authority is False


def test_authority_stolen_when_recorded_bench_is_in_dev_mode(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    authority_file.write_text("other-bench")
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)

    with patch("pilot.core.monitor.iter_sibling_benches", return_value=iter([_sibling("other-bench", "")])):
        assert monitor.is_system_log_authority is True
    assert authority_file.read_text() == "my-bench"


def test_authority_stolen_when_recorded_bench_no_longer_exists(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    authority_file.write_text("dropped-bench")
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)

    with patch("pilot.core.monitor.iter_sibling_benches", return_value=iter([])):
        assert monitor.is_system_log_authority is True
    assert authority_file.read_text() == "my-bench"


def test_exactly_one_bench_holds_authority(tmp_path: Path) -> None:
    """When two benches run, exactly one is the system-log authority."""
    authority_file = tmp_path / ".bench-authority"

    monitor_a = _make_monitor(_make_bench(tmp_path / "bench-a", "bench-a"), authority_file)
    monitor_b = _make_monitor(_make_bench(tmp_path / "bench-b", "bench-b"), authority_file)

    # bench-a claims authority (file absent)
    assert monitor_a.is_system_log_authority is True

    # bench-b sees bench-a as the running authority
    with patch("pilot.core.monitor.iter_sibling_benches", return_value=iter([_sibling("bench-a", "systemd")])):
        assert monitor_b.is_system_log_authority is False


# ── collect_system_metrics ───────────────────────────────────────────────────


def _fake_proc_reads(monitor: Monitor) -> None:
    """Stub out /proc reads so tests don't depend on the host machine state."""
    monitor._load_average = lambda: (0.5, 0.4, 0.3)  # type: ignore[method-assign]
    monitor._system_cpu_percent = lambda: 12.5  # type: ignore[method-assign]
    monitor._memory_usage = lambda: {"total_mb": 8192.0, "used_mb": 4096.0, "available_mb": 4096.0, "percent": 50.0}  # type: ignore[method-assign]


def test_collect_system_metrics_writes_to_system_log_file(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    system_log_file = tmp_path / "bench-system-stats.log"
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)
    monitor.bench.config.monitor.system_log_path = system_log_file
    _fake_proc_reads(monitor)

    monitor.collect_system_metrics()

    assert system_log_file.exists()
    entry = next(iter(json.loads(system_log_file.read_text()).values()))
    assert entry["load_avg"] == [0.5, 0.4, 0.3]
    assert entry["cpu_percent"] == 12.5
    assert entry["memory"]["percent"] == 50.0


def test_collect_system_metrics_does_not_write_app_log(tmp_path: Path) -> None:
    """System metrics must never bleed into the per-bench application log."""
    authority_file = tmp_path / ".bench-authority"
    system_log_file = tmp_path / "bench-system-stats.log"
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)
    monitor.bench.config.monitor.system_log_path = system_log_file
    _fake_proc_reads(monitor)

    monitor.collect_system_metrics()

    assert not monitor.log_path.exists()


def test_collect_system_metrics_skipped_when_not_authority(tmp_path: Path) -> None:
    authority_file = tmp_path / ".bench-authority"
    authority_file.write_text("other-bench")
    system_log_file = tmp_path / "bench-system-stats.log"
    monitor = _make_monitor(_make_bench(tmp_path / "my-bench"), authority_file)
    monitor.bench.config.monitor.system_log_path = system_log_file

    siblings = [_sibling("other-bench", "systemd")]
    with patch("pilot.core.monitor.iter_sibling_benches", return_value=iter(siblings)):
        monitor.collect_system_metrics()

    assert not system_log_file.exists()
