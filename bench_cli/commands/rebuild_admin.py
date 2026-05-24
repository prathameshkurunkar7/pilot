from __future__ import annotations

import shutil
from pathlib import Path

import click

from bench_cli.exceptions import BenchError
from bench_cli.utils import run_command


class RebuildAdminCommand:
    def run(self) -> None:
        frontend = self._find_frontend()
        click.echo(f"Building admin frontend at {frontend}...")
        if not (frontend / "node_modules").exists():
            click.echo("Running npm install...")
            run_command(["npm", "install"], cwd=frontend, stream_output=True)
        run_command(["npm", "run", "build"], cwd=frontend, stream_output=True)
        click.echo("\nAdmin frontend rebuilt successfully.")

    def _find_frontend(self) -> Path:
        for source in self._source_candidates():
            candidate = source / "admin" / "frontend"
            if (candidate / "package.json").exists():
                return candidate
        raise BenchError(
            "admin/frontend not found.\n"
            "This command requires the bench-cli source directory with admin/frontend/."
        )

    def _source_candidates(self):
        # 1. Standard location created by install.sh
        yield Path.home() / "bench-cli"

        # 2. Resolve via dist-info/direct_url.json — works whether the package
        #    was installed editable or from a local directory, and is unaffected
        #    by sys.path[0] shadowing when bench runs as a script.
        try:
            import importlib.metadata, json
            dist = importlib.metadata.distribution("bench-cli")
            direct_url_path = Path(str(dist._path)) / "direct_url.json"
            if direct_url_path.exists():
                info = json.loads(direct_url_path.read_text())
                url = info.get("url", "")
                if url.startswith("file://"):
                    yield Path(url[len("file://"):])
        except Exception:
            pass

        # 3. Fallback: __file__ of the bench_cli package (works when CWD is
        #    the source root and bench_cli is imported from there via sys.path).
        import bench_cli as _pkg
        yield Path(_pkg.__file__).parent.parent
