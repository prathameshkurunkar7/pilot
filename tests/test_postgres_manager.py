from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from bench_cli.config.postgres_config import PostgresConfig
from bench_cli.managers.postgres_manager import PostgresManager

MODULE = "bench_cli.managers.postgres_manager"


def _mgr(**kwargs) -> PostgresManager:
    return PostgresManager(PostgresConfig(**kwargs))


# ── install ───────────────────────────────────────────────────────────────────


def test_is_installed_checks_binaries() -> None:
    with patch(f"{MODULE}.which", side_effect=lambda n: "/usr/bin/psql" if n == "psql" else None):
        assert _mgr().is_installed() is True
    with patch(f"{MODULE}.which", return_value=None):
        assert _mgr().is_installed() is False


def test_install_skips_when_present() -> None:
    m = _mgr()
    with patch.object(m, "is_installed", return_value=True), patch(f"{MODULE}.get_package_manager") as gpm:
        m.install()
    gpm.assert_not_called()


def test_install_uses_apt_packages_on_linux() -> None:
    m, pkg = _mgr(), MagicMock()
    with patch.object(m, "is_installed", return_value=False), patch(f"{MODULE}.is_macos", return_value=False), patch(f"{MODULE}.get_package_manager", return_value=pkg):
        m.install()
    pkg.install.assert_called_once_with("postgresql", "postgresql-client")


def test_install_uses_brew_formula_on_macos() -> None:
    m, pkg = _mgr(version="16"), MagicMock()
    with patch.object(m, "is_installed", return_value=False), patch(f"{MODULE}.is_macos", return_value=True), patch.object(m, "_installed_brew_formula", return_value=None), patch(f"{MODULE}.get_package_manager", return_value=pkg):
        m.install()
    pkg.install.assert_called_once_with("postgresql@16")


# ── secure ────────────────────────────────────────────────────────────────────


def test_secure_skips_when_no_password() -> None:
    m = _mgr(root_password="")
    with patch.object(m, "check_credentials") as cc, patch.object(m, "_run_sql_as_superuser") as run:
        m.secure()
    cc.assert_not_called()
    run.assert_not_called()


def test_secure_noop_when_credentials_already_work() -> None:
    m = _mgr(root_password="pw")
    with patch.object(m, "check_credentials", return_value=True), patch.object(m, "_run_sql_as_superuser") as run:
        m.secure()
    run.assert_not_called()


def test_secure_sets_password_then_verifies() -> None:
    m = _mgr(root_password="pw")
    with patch.object(m, "check_credentials", side_effect=[False, True]), patch.object(m, "_run_sql_as_superuser") as run:
        m.secure()
    run.assert_called_once()


def test_secure_raises_when_still_unauthenticated() -> None:
    m = _mgr(root_password="pw")
    with patch.object(m, "check_credentials", side_effect=[False, False]), patch.object(m, "_run_sql_as_superuser"):
        with pytest.raises(RuntimeError, match="authenticate"):
            m.secure()


def test_ensure_role_sql_creates_or_alters_with_quoting() -> None:
    sql = _mgr(admin_user="postgres", root_password="p'w")._ensure_role_sql()
    assert 'CREATE ROLE "postgres" WITH LOGIN SUPERUSER PASSWORD' in sql
    assert 'ALTER ROLE "postgres" WITH LOGIN SUPERUSER PASSWORD' in sql
    assert "'p''w'" in sql  # single quote doubled for the SQL literal


# ── credentials check ──────────────────────────────────────────────────────────


def test_check_credentials_uses_pgpassword_and_tcp() -> None:
    m = _mgr(root_password="pw", host="h", port=5440, admin_user="pg")
    captured: dict = {}

    def fake_run(cmd, env=None, capture_output=None, text=None):
        captured["cmd"], captured["env"] = cmd, env
        return MagicMock(returncode=0)

    with patch(f"{MODULE}.which", return_value="/usr/bin/psql"), patch(f"{MODULE}.subprocess.run", side_effect=fake_run):
        assert m.check_credentials() is True
    assert captured["env"]["PGPASSWORD"] == "pw"
    cmd = captured["cmd"]
    assert cmd[cmd.index("-U") + 1] == "pg"
    assert cmd[cmd.index("-p") + 1] == "5440"
    assert cmd[cmd.index("-h") + 1] == "h"


def test_check_credentials_false_without_psql() -> None:
    with patch(f"{MODULE}.which", return_value=None), patch(f"{MODULE}.is_macos", return_value=False):
        assert _mgr(root_password="pw").check_credentials() is False


# ── service control & provisioning ─────────────────────────────────────────────


def test_start_targets_systemctl_on_linux() -> None:
    m = _mgr()
    with patch(f"{MODULE}.is_macos", return_value=False), patch(f"{MODULE}.run_command") as rc:
        m.start()
    rc.assert_called_once_with(["sudo", "systemctl", "start", "postgresql"])


def test_start_targets_brew_on_macos() -> None:
    m = _mgr()
    with patch(f"{MODULE}.is_macos", return_value=True), patch.object(m, "_installed_brew_formula", return_value="postgresql@16"), patch(f"{MODULE}.run_command") as rc:
        m.start()
    rc.assert_called_once_with(["brew", "services", "start", "postgresql@16"])


def test_provision_orchestrates_steps() -> None:
    m = _mgr(root_password="pw")
    with patch(f"{MODULE}.is_alpine", return_value=False), patch.object(m, "install") as ins, patch.object(m, "enable") as en, patch.object(m, "is_running", return_value=False), patch.object(m, "start") as st, patch.object(m, "_wait_until_reachable"), patch.object(m, "secure") as sec:
        m.provision()
    ins.assert_called_once()
    en.assert_called_once()
    st.assert_called_once()
    sec.assert_called_once()
