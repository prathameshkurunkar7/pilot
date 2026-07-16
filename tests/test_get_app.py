"""Tests for GetAppCommand.run() short-circuiting altogether when the app is
already registered in apps.txt — no clone, no validate, no install/build."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from pilot.commands.get_app import GetAppCommand
from pilot.core.marketplace import Marketplace, Resolver
from tests.test_commands import make_bench


def make_resolver(name: str, deps: dict[str, str] | None = None) -> Resolver:
    return Resolver(
        app=name,
        repo=f"https://github.com/frappe/{name}",
        target_type="branch",
        target="main",
        version="1.0.0",
        frappe_version="16.0.0",
        required_version="",
        is_installable=True,
        dependencies=deps or {},
    )


def make_command(tmp_path: Path, name: str = "myapp", **kwargs) -> GetAppCommand:
    bench = make_bench(tmp_path)
    bench.create_directories()
    cmd = GetAppCommand(bench, f"https://github.com/frappe/{name}", **kwargs)
    # Skip real cloning/installing/building — only run()'s early-return
    # decision is under test here.
    cmd._clone = lambda: None
    cmd._normalize_folder = lambda: None
    cmd._install = lambda: None
    cmd._register = lambda: None
    cmd._build = lambda: None
    return cmd


def test_full_flow_runs_when_app_not_registered(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    cmd = GetAppCommand(bench, "https://github.com/frappe/myapp")
    cmd._normalize_folder = lambda: None
    cmd._register = lambda: None

    with patch.object(GetAppCommand, "_validate") as mock_validate, \
            patch.object(GetAppCommand, "_clone") as mock_clone, \
            patch.object(GetAppCommand, "_install") as mock_install, \
            patch.object(GetAppCommand, "_build") as mock_build:
        cmd.run()

    mock_clone.assert_called_once()
    mock_validate.assert_called_once()
    mock_install.assert_called_once()
    mock_build.assert_called_once()


def test_run_short_circuits_when_app_already_registered(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    (bench.apps_path / "myapp").mkdir(parents=True)  # registered apps always have a real folder
    (bench.sites_path / "apps.txt").write_text("frappe\nmyapp\n")
    cmd = GetAppCommand(bench, "https://github.com/frappe/myapp")

    with patch.object(GetAppCommand, "_validate") as mock_validate, \
            patch.object(GetAppCommand, "_clone") as mock_clone, \
            patch.object(GetAppCommand, "_install") as mock_install, \
            patch.object(GetAppCommand, "_build") as mock_build:
        cmd.run()

    mock_clone.assert_not_called()
    mock_validate.assert_not_called()
    mock_install.assert_not_called()
    mock_build.assert_not_called()


def test_short_circuit_adopts_real_on_disk_app_path(tmp_path: Path) -> None:
    """Regression: a hyphenated repo name's raw path never existed on disk —
    only the module-normalized folder from an earlier run does. cmd.app must
    point at the real folder so callers (e.g. get_and_install_app_task) don't
    get an App referencing a nonexistent path."""
    bench = make_bench(tmp_path)
    bench.create_directories()
    real_app_dir = bench.apps_path / "india_compliance"
    real_app_dir.mkdir(parents=True)
    (bench.sites_path / "apps.txt").write_text("frappe\nindia_compliance\n")

    cmd = GetAppCommand(bench, "https://github.com/frappe/india-compliance")
    cmd.run()

    assert cmd.app.path == real_app_dir
    assert cmd.app.path.is_dir()
    assert cmd.name == "india_compliance"


def test_short_circuit_still_populates_installed_dependencies(tmp_path: Path) -> None:
    """Defect: when run() short-circuits on an already-registered app,
    installed_dependencies must still list its marketplace dependencies —
    otherwise GetAndInstallAppTask only installs the primary app onto new
    sites and silently leaves its dependencies uninstalled there."""
    bench = make_bench(tmp_path)
    bench.create_directories()
    (bench.apps_path / "helpdesk").mkdir(parents=True)
    (bench.apps_path / "telephony").mkdir(parents=True)
    (bench.sites_path / "apps.txt").write_text("frappe\ntelephony\nhelpdesk\n")

    telephony = make_resolver("telephony")
    helpdesk = make_resolver("helpdesk", deps={"telephony": ""})
    helpdesk._registry = {"telephony": [telephony]}

    with patch.object(Marketplace, "read_all_apps", return_value=[helpdesk]), \
            patch.object(Marketplace, "get_current_frappe_version", return_value="16.0.0"), \
            patch("pilot.commands.get_app.GetAppCommand") as mock_cmd:
        cmd = GetAppCommand(bench, "https://github.com/frappe/helpdesk", install_dependencies=True)
        cmd.run()

    assert [app.config.name for app in cmd.installed_dependencies] == ["telephony"]
    mock_cmd.assert_not_called()


def test_short_circuit_never_installs_a_missing_dependency(tmp_path: Path) -> None:
    """An already-installed app is never re-installed, and neither are its
    dependencies — even if one is genuinely missing from the bench, the
    short-circuit path only resolves, it must never install."""
    bench = make_bench(tmp_path)
    bench.create_directories()
    (bench.apps_path / "helpdesk").mkdir(parents=True)
    (bench.sites_path / "apps.txt").write_text("frappe\nhelpdesk\n")  # telephony missing

    telephony = make_resolver("telephony")
    helpdesk = make_resolver("helpdesk", deps={"telephony": ""})
    helpdesk._registry = {"telephony": [telephony]}

    with patch.object(Marketplace, "read_all_apps", return_value=[helpdesk]), \
            patch.object(Marketplace, "get_current_frappe_version", return_value="16.0.0"), \
            patch("pilot.commands.get_app.GetAppCommand") as mock_cmd:
        cmd = GetAppCommand(bench, "https://github.com/frappe/helpdesk", install_dependencies=True)
        cmd.run()

    mock_cmd.assert_not_called()
    assert cmd.installed_dependencies == []


def test_skip_validations_flag_still_skips_validate(tmp_path: Path) -> None:
    cmd = make_command(tmp_path, skip_validations=True)

    with patch.object(GetAppCommand, "_validate") as mock_validate:
        cmd.run()

    mock_validate.assert_not_called()


def test_bench_is_app_installed_reflects_apps_txt_contents(tmp_path: Path) -> None:
    bench = make_bench(tmp_path)
    bench.create_directories()
    assert bench.is_app_installed("erpnext") is False

    (bench.sites_path / "apps.txt").write_text("frappe\nerpnext\n")
    assert bench.is_app_installed("erpnext") is True
