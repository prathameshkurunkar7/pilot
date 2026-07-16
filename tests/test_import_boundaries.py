"""Static import-boundary checks for the package split done in Milestone 10.

These parse source with `ast` rather than actually importing modules, so a
violation is caught even if the forbidden import is guarded by a runtime
condition that never triggers in tests.
"""
from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
PILOT_ROOT = REPO_ROOT / "pilot"


def _imported_module_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            names.add(node.module)
    return names


def _is_or_starts_with(module: str, package: str) -> bool:
    return module == package or module.startswith(f"{package}.")


def _violations(root: Path, forbidden_packages: tuple[str, ...]) -> list[str]:
    problems = []
    for path in sorted(root.rglob("*.py")):
        for module in _imported_module_names(path):
            if any(_is_or_starts_with(module, pkg) for pkg in forbidden_packages):
                problems.append(f"{path.relative_to(REPO_ROOT)} imports {module!r}")
    return problems


def test_pilot_never_imports_admin_backend_or_flask() -> None:
    """pilot is the Flask-free CLI/library layer; admin.backend depends on it,
    not the reverse. pilot spawns admin.backend as a subprocess by module-path
    string (e.g. `python -m admin.backend.server`) — that's a string argv entry,
    not an import, so it doesn't trip this check."""
    violations = _violations(PILOT_ROOT, ("admin.backend", "flask"))
    assert violations == []


def test_task_engine_never_imports_admin_backend() -> None:
    """Narrower regression guard for the pilot/tasks move in 10.1: the task
    engine specifically must stay importable without admin.backend on the path."""
    violations = _violations(PILOT_ROOT / "tasks", ("admin.backend", "flask"))
    assert violations == []
