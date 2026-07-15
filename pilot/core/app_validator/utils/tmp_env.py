from __future__ import annotations

import shutil
import tempfile
import typing
from pathlib import Path

from pilot.exceptions import AppValidationError, BenchError, CommandError
from pilot.utils import run_command

if typing.TYPE_CHECKING:
    from pilot.core.app import App


class TmpEnv:
    """A throwaway venv an app is installed into, to validate the install
    succeeds before it touches the bench's real environment."""

    def __init__(self) -> None:
        self._dir: str | None = None

    @property
    def path(self) -> Path:
        if self._dir is None:
            raise BenchError("Temporary environment not created yet.")
        return Path(self._dir)

    def create(self, frappe_path: Path) -> "TmpEnv":
        self._dir = tempfile.mkdtemp(prefix="pilot-app-validate-")
        run_command([self._uv(), "venv", str(self.path)], stream_output=True)
        try:
            self._pip_install([frappe_path])
        except CommandError as exc:
            raise AppValidationError(
                f"Failed to install frappe into the validation env:\n{exc.message}"
            )
        return self

    def install_app(self, app: "App") -> None:
        try:
            self._pip_install([app.path])
        except CommandError as exc:
            raise AppValidationError(f"'{app.config.name}' failed to install:\n{exc.message}")

    def resolve_modules(self, module_names: list[str]) -> None:
        try:
            run_command(
                [str(self.path / "bin" / "python"), "-c", self._resolve_check_script(module_names)]
            )
        except CommandError as exc:
            raise AppValidationError(f"Import errors:\n{exc.message}")

    @staticmethod
    def _resolve_check_script(module_names: list[str]) -> str:
        # Resolves each module via find_spec instead of importing it, so we
        # catch missing/renamed modules without running their top-level code.
        return (
            "import importlib.util, sys\n"
            "errors = []\n"
            f"for name in {module_names!r}:\n"
            "    try:\n"
            "        if importlib.util.find_spec(name) is None:\n"
            "            raise ModuleNotFoundError(f'No module named {name!r}')\n"
            "    except Exception as exc:\n"
            "        errors.append(f'{name}: {exc}')\n"
            "if errors:\n"
            "    sys.exit('\\n'.join(errors))\n"
        )

    def _pip_install(self, paths: list[Path]) -> None:
        python = str(self.path / "bin" / "python")
        run_command([self._uv(), "pip", "install", "--python", python, *map(str, paths)])

    def delete(self) -> None:
        if self._dir is not None:
            shutil.rmtree(self._dir, ignore_errors=True)
            self._dir = None

    @staticmethod
    def _uv() -> str:
        uv = shutil.which("uv")
        if not uv:
            raise BenchError("uv not found — run the pilot install script to set it up")
        return uv
