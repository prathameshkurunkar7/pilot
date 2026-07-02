"""Tests for admin.backend.tasks.jobs.fetch_app_updates_task.

Covers the marketplace pinning logic: an app is excluded from the update
check only while it sits on the fixed (tag/commit) revision the marketplace
pins it to. A branch target, a moved tag/commit, a repo/version mismatch, or
a non-marketplace app all stay updatable.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from admin.backend.readers.app_reader import AppReader
from admin.backend.tasks.jobs.fetch_app_updates_task import FetchAppUpdatesTask
from pilot.core.marketplace import Marketplace


def app_mock(repo: str, version: str = "", installed_hash: str = "", installed_tag: str = "") -> MagicMock:
    app = MagicMock()
    app.config.repo = repo
    app.installed_version = version
    app.installed_hash = installed_hash
    app.installed_tag = installed_tag
    return app


def make_task(registry: list[dict], bench: MagicMock, bench_root: Path) -> FetchAppUpdatesTask:
    with patch.object(Marketplace, "registry", return_value=registry):
        return FetchAppUpdatesTask(bench, bench_root, MagicMock())


# ── _is_on_target_revision ───────────────────────────────────────────────────


def test_on_target_revision_tag_matches() -> None:
    app = app_mock("r", installed_tag="v1.0.0")
    assert FetchAppUpdatesTask._is_on_target_revision(app, {"target_type": "tag", "target": "v1.0.0"})


def test_on_target_revision_tag_differs() -> None:
    app = app_mock("r", installed_tag="v0.9.0")
    assert not FetchAppUpdatesTask._is_on_target_revision(app, {"target_type": "tag", "target": "v1.0.0"})


def test_on_target_revision_no_tag_at_head() -> None:
    app = app_mock("r", installed_hash="deadbeef", installed_tag="")
    assert not FetchAppUpdatesTask._is_on_target_revision(app, {"target_type": "tag", "target": "v1.0.0"})


def test_on_target_revision_commit_prefix_matches() -> None:
    # Registry may store an abbreviated hash; a full HEAD sha that starts with it counts.
    app = app_mock("r", installed_hash="abc123def456")
    assert FetchAppUpdatesTask._is_on_target_revision(app, {"target_type": "commit", "target": "abc123"})


def test_on_target_revision_commit_differs() -> None:
    app = app_mock("r", installed_hash="999999aaaa")
    assert not FetchAppUpdatesTask._is_on_target_revision(app, {"target_type": "commit", "target": "abc123"})


def test_on_target_revision_commit_empty_head() -> None:
    app = app_mock("r", installed_hash="")
    assert not FetchAppUpdatesTask._is_on_target_revision(app, {"target_type": "commit", "target": "abc123"})


def test_on_target_revision_branch_never_pins() -> None:
    app = app_mock("r", installed_hash="abc123", installed_tag="main")
    assert not FetchAppUpdatesTask._is_on_target_revision(app, {"target_type": "branch", "target": "main"})


# ── _is_pinned_by_marketplace ────────────────────────────────────────────────


TAG_REGISTRY = [
    {"name": "helpdesk", "repo": "https://github.com/frappe/helpdesk", "targets": [
        {"version": "1.0.0", "target_type": "tag", "target": "v1.0.0"},
    ]},
]
COMMIT_REGISTRY = [
    {"name": "payments", "repo": "https://github.com/frappe/payments", "targets": [
        {"version": "2.0.0", "target_type": "commit", "target": "abc123"},
    ]},
]
BRANCH_REGISTRY = [
    {"name": "hrms", "repo": "https://github.com/frappe/hrms", "targets": [
        {"version": "3.0.0", "target_type": "branch", "target": "main"},
    ]},
]


def _task(registry: list[dict], name: str, app: MagicMock, tmp_path: Path) -> FetchAppUpdatesTask:
    bench = MagicMock()
    bench.app.side_effect = lambda n: app if n == name else MagicMock()
    return make_task(registry, bench, tmp_path)


def test_pinned_when_on_pinned_tag(tmp_path: Path) -> None:
    app = app_mock("https://github.com/frappe/helpdesk", "1.0.0", installed_tag="v1.0.0")
    task = _task(TAG_REGISTRY, "helpdesk", app, tmp_path)
    assert task._is_pinned_by_marketplace("helpdesk") is True


def test_not_pinned_when_tag_moved(tmp_path: Path) -> None:
    # Marketplace points at v1.0.0 but the app sits on v0.9.0 — allow the upgrade.
    app = app_mock("https://github.com/frappe/helpdesk", "1.0.0", installed_tag="v0.9.0")
    task = _task(TAG_REGISTRY, "helpdesk", app, tmp_path)
    assert task._is_pinned_by_marketplace("helpdesk") is False


def test_pinned_when_on_pinned_commit(tmp_path: Path) -> None:
    app = app_mock("https://github.com/frappe/payments", "2.0.0", installed_hash="abc123def456")
    task = _task(COMMIT_REGISTRY, "payments", app, tmp_path)
    assert task._is_pinned_by_marketplace("payments") is True


def test_not_pinned_when_commit_moved(tmp_path: Path) -> None:
    app = app_mock("https://github.com/frappe/payments", "2.0.0", installed_hash="fedcba987654")
    task = _task(COMMIT_REGISTRY, "payments", app, tmp_path)
    assert task._is_pinned_by_marketplace("payments") is False


def test_branch_target_never_pinned(tmp_path: Path) -> None:
    app = app_mock("https://github.com/frappe/hrms", "3.0.0", installed_hash="deadbeef")
    task = _task(BRANCH_REGISTRY, "hrms", app, tmp_path)
    assert task._is_pinned_by_marketplace("hrms") is False


def test_not_pinned_when_version_mismatch(tmp_path: Path) -> None:
    # Installed version doesn't match the pinned target's version — not that target.
    app = app_mock("https://github.com/frappe/helpdesk", "9.9.9", installed_tag="v1.0.0")
    task = _task(TAG_REGISTRY, "helpdesk", app, tmp_path)
    assert task._is_pinned_by_marketplace("helpdesk") is False


def test_not_pinned_when_repo_mismatch(tmp_path: Path) -> None:
    # A fork with a different repo URL isn't the marketplace's app.
    app = app_mock("https://github.com/someone/helpdesk", "1.0.0", installed_tag="v1.0.0")
    task = _task(TAG_REGISTRY, "helpdesk", app, tmp_path)
    assert task._is_pinned_by_marketplace("helpdesk") is False


def test_unknown_app_not_pinned_without_touching_git(tmp_path: Path) -> None:
    # Apps absent from the registry must short-circuit before the (costly) bench.app() call.
    bench = MagicMock()
    task = make_task(TAG_REGISTRY, bench, tmp_path)
    assert task._is_pinned_by_marketplace("frappe") is False
    bench.app.assert_not_called()


# ── run ──────────────────────────────────────────────────────────────────────


def _make_git_apps(bench_root: Path, names: list[str]) -> None:
    for name in names:
        (bench_root / "apps" / name / ".git").mkdir(parents=True)


def test_run_excludes_pinned_and_reports_the_rest(tmp_path: Path, capsys) -> None:
    _make_git_apps(tmp_path, ["erpnext", "payments", "helpdesk"])
    registry = COMMIT_REGISTRY + BRANCH_REGISTRY  # payments (commit) + hrms (unused here)
    apps = {
        "erpnext": app_mock("https://github.com/frappe/erpnext", "15.0.0"),          # not in registry
        "payments": app_mock("https://github.com/frappe/payments", "2.0.0", installed_hash="abc123def"),  # on pinned commit
        "helpdesk": app_mock("https://github.com/frappe/helpdesk", "1.0.0", installed_hash="x"),           # not in registry
    }
    bench = MagicMock()
    bench.app.side_effect = lambda n: apps[n]

    check = MagicMock(side_effect=lambda names: {n: False for n in names})
    with patch.object(Marketplace, "registry", return_value=registry), \
            patch.object(AppReader, "check_remote_updates", check):
        task = FetchAppUpdatesTask(bench, tmp_path, MagicMock())
        task.run()

    checked = set(check.call_args.args[0])
    assert checked == {"erpnext", "helpdesk"}  # payments excluded (pinned)

    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert set(result) == {"erpnext", "helpdesk"}


def test_run_includes_app_whose_pinned_commit_moved(tmp_path: Path, capsys) -> None:
    _make_git_apps(tmp_path, ["payments"])
    apps = {"payments": app_mock("https://github.com/frappe/payments", "2.0.0", installed_hash="different")}
    bench = MagicMock()
    bench.app.side_effect = lambda n: apps[n]

    check = MagicMock(side_effect=lambda names: {n: True for n in names})
    with patch.object(Marketplace, "registry", return_value=COMMIT_REGISTRY), \
            patch.object(AppReader, "check_remote_updates", check):
        task = FetchAppUpdatesTask(bench, tmp_path, MagicMock())
        task.run()

    assert set(check.call_args.args[0]) == {"payments"}
    result = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert result == {"payments": True}


def test_run_ignores_non_git_dirs(tmp_path: Path, capsys) -> None:
    (tmp_path / "apps" / "erpnext" / ".git").mkdir(parents=True)
    (tmp_path / "apps" / "not_an_app").mkdir(parents=True)  # no .git
    bench = MagicMock()
    bench.app.side_effect = lambda n: app_mock("r", "1.0.0")

    check = MagicMock(side_effect=lambda names: {n: False for n in names})
    with patch.object(Marketplace, "registry", return_value=[]), \
            patch.object(AppReader, "check_remote_updates", check):
        FetchAppUpdatesTask(bench, tmp_path, MagicMock()).run()

    assert set(check.call_args.args[0]) == {"erpnext"}
