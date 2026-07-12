from __future__ import annotations

import ast
import sys
import tomllib
import typing
from pathlib import Path

from pilot.exceptions import AppValidationError

if typing.TYPE_CHECKING:
    from pilot.core.app import App


class Validator:
    """Statically validates a cloned app before it's installed into the bench
    env, so a broken app is rejected up front instead of after `pip install`
    has already touched the environment."""

    def __init__(self, app: "App"):
        self.app = app
        self.module_path = app.path / app.module_name

    def validate(self) -> None:
        self.validate_repo_structure()
        self.validate_internal_imports()
        self.validate_external_imports()

    def validate_repo_structure(self) -> None:
        if not (self.app.path / "pyproject.toml").exists():
            raise AppValidationError(f"'{self.app.config.name}' has no pyproject.toml.")
        if not self.module_path.is_dir():
            raise AppValidationError(f"'{self.app.config.name}' has no '{self.app.module_name}' package directory.")
        if not (self.module_path / "hooks.py").exists():
            raise AppValidationError(f"'{self.app.config.name}' is missing {self.app.module_name}/hooks.py.")

    def validate_internal_imports(self) -> None:
        broken = [
            f"{path.relative_to(self.app.path)}: {module}"
            for path, module in self._all_imports()
            if self._is_internal(module) and not self._resolves(module)
        ]
        if broken:
            raise AppValidationError(
                f"'{self.app.config.name}' has broken internal imports:\n" + "\n".join(f"  {b}" for b in broken)
            )

    def validate_external_imports(self) -> None:
        declared = self._declared_dependencies()
        missing = sorted(
            {
                self._top_level_package(module)
                for _, module in self._all_imports()
                if self._is_external(module) and self._top_level_package(module) not in declared
            }
        )
        if missing:
            raise AppValidationError(
                f"'{self.app.config.name}' imports packages not declared as dependencies: {', '.join(missing)}"
            )

    def _all_imports(self) -> list[tuple[Path, str]]:
        return [(path, module) for path in self._python_files() for module in self._imported_modules(path)]

    def _python_files(self) -> list[Path]:
        return list(self.module_path.rglob("*.py"))

    def _is_internal(self, module: str) -> bool:
        return module.startswith(self.app.module_name)

    @staticmethod
    def _top_level_package(module: str) -> str:
        return module.split(".")[0]

    @staticmethod
    def _imported_modules(path: Path) -> list[str]:
        try:
            tree = ast.parse(path.read_text(), filename=str(path))
        except (SyntaxError, OSError):
            return []
        modules = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                modules.append(node.module)
        return modules

    def _resolves(self, module: str) -> bool:
        parts = module.split(".")
        candidate = self.app.path.joinpath(*parts)
        return candidate.with_suffix(".py").exists() or (candidate / "__init__.py").exists()

    def _is_external(self, module: str) -> bool:
        root = self._top_level_package(module)
        return root != self.app.module_name and root not in sys.stdlib_module_names

    def _declared_dependencies(self) -> set[str]:
        pyproject = self.app.path / "pyproject.toml"
        try:
            data = tomllib.loads(pyproject.read_text())
        except (tomllib.TOMLDecodeError, OSError):
            return set()
        names = {self._dependency_name(dep) for dep in data.get("project", {}).get("dependencies", [])}
        names.add("frappe")
        return names

    @staticmethod
    def _dependency_name(requirement: str) -> str:
        import re

        name = re.split(r"[<>=!~\[; ]", requirement, maxsplit=1)[0]
        return name.strip().replace("-", "_")
