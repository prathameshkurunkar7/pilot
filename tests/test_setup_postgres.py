"""Wizard-side PostgreSQL handling: password validation in admin/backend/views/setup.py."""

from __future__ import annotations

from pathlib import Path

from admin.backend.views.setup import _read_defaults, _validate


# ── _validate ───────────────────────────────────────────────────────────────────


def test_validate_requires_postgres_password() -> None:
    error = _validate({"admin_password": "x", "db_type": "postgres", "postgres_password": ""})
    assert error and "postgres_password" in error


def test_validate_accepts_postgres_password() -> None:
    data = {"admin_password": "x", "db_type": "postgres", "postgres_password": "pw"}
    assert _validate(data) is None


def test_validate_requires_mariadb_password() -> None:
    error = _validate({"admin_password": "x", "db_type": "mariadb", "mariadb_password": ""})
    assert error and "mariadb_password" in error


# ── _read_defaults ────────────────────────────────────────────────────────────


def test_read_defaults_omits_password_fallbacks_for_fresh_bench(tmp_path: Path) -> None:
    """No bench.toml yet — the wizard must not see the CLI's 'root' fallback as
    an already-chosen password, or it'll skip generating its own."""
    result = _read_defaults(tmp_path)
    assert "mariadb_password" not in result
    assert "postgres_password" not in result


def test_read_defaults_never_leaks_a_real_saved_password(tmp_path: Path) -> None:
    """Even a real, already-saved password must never come back over this
    endpoint — it's polled before login."""
    from admin.backend.views.setup import BenchTomlStore

    store = BenchTomlStore(tmp_path / "bench.toml")
    store.write_flat("bench6", {"mariadb_password": "s3cr3t", "postgres_password": "s3cr3t"})

    result = _read_defaults(tmp_path)
    assert "mariadb_password" not in result
    assert "postgres_password" not in result
