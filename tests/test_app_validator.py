"""Tests for Validator's pre-install static checks on a cloned app."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from pilot.config.app_config import AppConfig
from pilot.core.app import App
from pilot.core.app_validator import Validator
from pilot.exceptions import AppValidationError


@dataclass
class _FakeBench:
    apps_path: Path


def _make_app(bench_root: Path, name: str, pyproject: str, files: dict[str, str]) -> App:
    app_path = bench_root / "apps" / name
    app_path.mkdir(parents=True)
    (app_path / "pyproject.toml").write_text(pyproject)
    for relpath, content in files.items():
        full = app_path / relpath
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content)
    bench = _FakeBench(apps_path=bench_root / "apps")
    return App(AppConfig(name=name, repo=f"https://example.com/{name}.git", branch="main"), bench)


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
    Validator(app).validate()


def test_validate_repo_structure_fails_without_pyproject(tmp_path: Path) -> None:
    app_path = tmp_path / "apps" / "myapp"
    app_path.mkdir(parents=True)
    bench = _FakeBench(apps_path=tmp_path / "apps")
    app = App(AppConfig(name="myapp", repo="https://example.com/myapp.git", branch="main"), bench)
    with pytest.raises(AppValidationError, match="pyproject.toml"):
        Validator(app).validate()


def test_validate_repo_structure_fails_without_hooks(tmp_path: Path) -> None:
    app = _make_app(tmp_path, "myapp", '[project]\nname = "myapp"\n', {"myapp/__init__.py": ""})
    with pytest.raises(AppValidationError, match="hooks.py"):
        Validator(app).validate()


def test_validate_internal_imports_fails_on_broken_reference(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/utils.py": "from myapp.missing_module import thing\n",
        },
    )
    with pytest.raises(AppValidationError, match="broken internal imports"):
        Validator(app).validate()


def test_validate_external_imports_fails_on_undeclared_dependency(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/utils.py": "import numpy\n",
        },
    )
    with pytest.raises(AppValidationError, match="numpy"):
        Validator(app).validate()


def test_validate_passes_with_stdlib_and_frappe_imports(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/utils.py": "import os\nimport json\nimport frappe\n",
        },
    )
    Validator(app).validate()


def test_validate_passes_for_submodule_dependency_name(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\ndependencies = ["Pillow>=9"]\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/utils.py": "from PIL import Image\n",
        },
    )
    with pytest.raises(AppValidationError, match="PIL"):
        Validator(app).validate()


def test_validate_internal_imports_passes_for_resolvable_package_import(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/sub/__init__.py": "",
            "myapp/utils.py": "import myapp.sub\n",
        },
    )
    Validator(app).validate()


def test_validate_internal_imports_ignores_relative_imports(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/sub/__init__.py": "",
            "myapp/sub/utils.py": "from . import missing\n",
        },
    )
    Validator(app).validate()


def test_validate_external_imports_reports_all_missing_dependencies(tmp_path: Path) -> None:
    app = _make_app(
        tmp_path,
        "myapp",
        '[project]\nname = "myapp"\n',
        {
            "myapp/hooks.py": "app_name = 'myapp'\n",
            "myapp/utils.py": "import numpy\nimport pandas\n",
        },
    )
    with pytest.raises(AppValidationError, match="numpy, pandas"):
        Validator(app).validate()
