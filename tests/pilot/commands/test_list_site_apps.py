from __future__ import annotations

from types import SimpleNamespace

import pytest

from pilot.commands.sites.list_apps import _query_via_db_cli


def test_database_password_uses_environment_instead_of_argv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    password = "database-process-secret"
    captured = {}
    monkeypatch.setattr("pilot.commands.sites.list_apps.shutil.which", lambda name: "/usr/bin/mariadb")
    monkeypatch.setattr("pilot.commands.sites.list_apps.Path.exists", lambda path: False)

    def run(argv, **kwargs):
        captured["argv"] = argv
        captured["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="frappe\n")

    monkeypatch.setattr("pilot.commands.sites.list_apps.subprocess.run", run)

    result = _query_via_db_cli(
        {
            "db_name": "site_db",
            "db_password": password,
            "db_host": "127.0.0.1",
        }
    )

    assert result == ["frappe"]
    assert password not in "\0".join(captured["argv"])
    assert captured["env"]["MYSQL_PWD"] == password
