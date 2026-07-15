"""Tests for Validator's pre-install static checks on a cloned app."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from pilot.config.app_config import AppConfig
from pilot.core.app import App
from pilot.core.app_validator import Validator
from pilot.core.app_validator.dependency_declarations import DependencyDeclarationsCheck
from pilot.core.app_validator.imports import ImportCheck
from pilot.core.app_validator.repo_structure import RepoStructureCheck
from pilot.core.app_validator.syntax import SyntaxCheck
from pilot.exceptions import AppValidationError


@dataclass
class _FakeBench:
    apps_path: Path
    env_path: Path


def _make_app(bench_root: Path, name: str, pyproject: str, files: dict[str, str]) -> App:
    app_path = bench_root / "apps" / name
    app_path.mkdir(parents=True)
    (app_path / "pyproject.toml").write_text(pyproject)
    for relpath, content in files.items():
        full = app_path / relpath
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    bench = _FakeBench(apps_path=bench_root / "apps", env_path=bench_root / "env")
    return App(AppConfig(name=name, repo=f"https://example.com/{name}.git", branch="main"), bench)


def _static_checks() -> list:
    """RepoStructureCheck, SyntaxCheck and DependencyDeclarationsCheck only —
    excludes ImportCheck, which installs into a real throwaway venv and needs
    a real frappe checkout, making it an integration concern, not a unit test."""
    return [RepoStructureCheck(), SyntaxCheck(), DependencyDeclarationsCheck()]


def test_validate_passes_for_well_formed_app(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\ndependencies = ["requests>=2"]\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/utils.py": "import requests\nfrom myapp.hooks import app_name\n",
        },
    )
    Validator(app, checks=_static_checks()).validate()


def test_validate_includes_import_check_by_default(tmp_path: Path) -> None:
    app = _make_app(tmp_path, "myapp", '[project]\nname = "myapp"\n', {"myapp/hooks.py": ""})
    assert any(isinstance(check, ImportCheck) for check in Validator(app).checks)


def test_validate_repo_structure_fails_without_pyproject(tmp_path: Path) -> None:
    app_path = tmp_path / "apps" / "myapp"
    app_path.mkdir(parents=True)
    bench = _FakeBench(apps_path=tmp_path / "apps", env_path=tmp_path / "env")
    app = App(AppConfig(name="myapp", repo="https://example.com/myapp.git", branch="main"), bench)
    with pytest.raises(AppValidationError, match="pyproject.toml"):
        Validator(app).validate()


def test_validate_repo_structure_fails_without_hooks(tmp_path: Path) -> None:
    app = _make_app(tmp_path, "myapp", '[project]\nname = "myapp"\n', {"myapp/__init__.py": ""})
    with pytest.raises(AppValidationError, match="hooks.py"):
        Validator(app).validate()


def test_validate_syntax_fails_on_broken_python_file(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/utils.py": "def broken(:\n    pass\n",
        },
    )
    with pytest.raises(AppValidationError, match="syntax errors"):
        Validator(app).validate()


def test_dependency_declarations_passes_when_required_app_is_declared(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n\n[tool.bench.frappe-dependencies]\nerpnext = ">=15"\n',
        {"myapp/hooks.py": 'required_apps = ["frappe/erpnext"]\n'},
    )
    Validator(app, checks=_static_checks()).validate()


def test_dependency_declarations_fails_when_required_app_is_missing(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n\n[tool.bench.frappe-dependencies]\nfrappe = ">=15"\n',
        {"myapp/hooks.py": 'required_apps = ["frappe/erpnext"]\n'},
    )
    with pytest.raises(AppValidationError, match="erpnext"):
        Validator(app, checks=_static_checks()).validate()
