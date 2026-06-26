"""End-to-end coverage for non-default Frappe database backends.

The CI workflow provisions one clean bench per backend, then this module
creates a site through bench-cli and verifies that Frappe can migrate it.
"""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest


ENGINE = os.environ.get("INTEGRATION_DATABASE_ENGINE", "")
SITE = "backend-test.localhost"


def _run(bench_bin: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([bench_bin, *args], cwd=cwd, capture_output=True, text=True)


@pytest.mark.integration
@pytest.mark.parametrize("engine", [ENGINE] if ENGINE else [])
def test_create_and_migrate_site_with_selected_database(
    bench_root: Path, bench_bin: str, engine: str
) -> None:
    """Create a site using the configured backend and run its first migration."""
    assert engine in {"postgres", "sqlite"}

    result = _run(bench_bin, "new-site", SITE, "--admin-password", "admin", cwd=bench_root)
    assert result.returncode == 0, result.stdout + result.stderr

    site_config = json.loads((bench_root / "sites" / SITE / "site_config.json").read_text())
    assert site_config["db_type"] == engine
    if engine == "sqlite":
        assert (bench_root / "sites" / SITE / "db" / f"{site_config['db_name']}.db").is_file()

    result = _run(bench_bin, "--site", SITE, "migrate", cwd=bench_root)
    assert result.returncode == 0, result.stdout + result.stderr
