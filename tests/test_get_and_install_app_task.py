"""Tests for admin.backend.tasks.jobs.get_and_install_app_task.GetAndInstallAppTask.

Only the requested app itself gets installed on sites — Frappe's own
`site install-app` already cascades installing declared dependencies, so
installing them here too (as get-app's installed_dependencies used to
drive) was a redundant no-op per site, and a redundant asset rebuild.
"""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from admin.backend.tasks.jobs.get_and_install_app_task import GetAndInstallAppTask
from pilot.core.site import Site
from tests.test_commands import make_bench


def make_task(bench_root: Path, sites: list[str]) -> GetAndInstallAppTask:
    args = MagicMock(repo="https://github.com/frappe/helpdesk", branch="", marketplace_app="", sites=sites)
    bench = make_bench(bench_root)
    bench.create_directories()
    return GetAndInstallAppTask(bench, bench_root, args)


def test_install_on_sites_only_installs_the_given_app(tmp_path: Path) -> None:
    task = make_task(tmp_path, ["site1.localhost"])
    app = MagicMock()
    app.config.name = "helpdesk"

    with patch.object(Site, "install_app") as mock_install, \
            patch("pilot.managers.python_env_manager.PythonEnvManager.build_assets_for_app") as mock_build:
        task._install_on_sites(app)

    mock_install.assert_called_once_with(app)
    mock_build.assert_called_once_with(app)


def test_run_never_touches_installed_dependencies(tmp_path: Path) -> None:
    """Regression: run() must only pass cmd.app to _install_on_sites, never
    cmd.installed_dependencies — those are already fully installed (with
    assets built) via get-app's own dependency flow, and Frappe's site
    install-app cascades installing them for the site automatically."""
    task = make_task(tmp_path, ["site1.localhost"])

    fake_cmd = MagicMock()
    fake_cmd.app.config.name = "helpdesk"
    fake_cmd.installed_dependencies = [MagicMock()]  # would break the old behaviour if touched

    with patch.object(task, "_fetch", return_value=fake_cmd), \
            patch.object(task, "_install_on_sites") as mock_install_on_sites:
        task.run()

    mock_install_on_sites.assert_called_once_with(fake_cmd.app)
