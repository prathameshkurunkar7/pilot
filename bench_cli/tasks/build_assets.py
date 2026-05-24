"""
Shared helper: install JS deps and build assets for a frappe app.

App root and frontend are treated as completely separate JS projects —
they may have different dependency trees and must not share node_modules.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def build_app_assets(bench_root: Path, app_name: str) -> None:
    app_dir = bench_root / "apps" / app_name
    sites_dir = bench_root / "sites"
    bench_bin = str(bench_root / "env" / "bin" / "bench")

    if not (app_dir / "package.json").exists():
        return  # no JS assets at all

    frontend_dir = app_dir / "frontend"
    has_separate_frontend = (frontend_dir / "package.json").exists()

    # ── App-root install ──────────────────────────────────────────────────────
    # Use --ignore-scripts so the root install doesn't accidentally trigger a
    # frontend install via postinstall hooks. We handle the frontend separately.
    print(f"\n[{app_name}] Installing app-root JS dependencies...")
    sys.stdout.flush()
    subprocess.run(
        ["yarn", "install", "--ignore-scripts"],
        cwd=str(app_dir),
        check=False,
    )

    # ── Frontend install (separate) ───────────────────────────────────────────
    if has_separate_frontend:
        print(f"\n[{app_name}] Installing frontend JS dependencies (separate env)...")
        sys.stdout.flush()
        subprocess.run(
            ["yarn", "install"],
            cwd=str(frontend_dir),
            check=False,
        )

    # ── Asset build ───────────────────────────────────────────────────────────
    # bench frappe build handles:
    #   1. Symlinking app's public/ into sites/assets/
    #   2. Running esbuild for root-level JS (public/*.js)
    #   3. Running the app's "build" script (which for apps like gameplan
    #      is "cd frontend && yarn build")
    # Since we already installed the frontend env above, step 3 uses the
    # freshly resolved node_modules and won't re-install.
    print(f"\n[{app_name}] Building assets...")
    sys.stdout.flush()
    subprocess.run(
        [bench_bin, "frappe", "build", "--app", app_name],
        cwd=str(sites_dir),
        check=False,
    )
