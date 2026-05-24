"""
Installs an app into a site then rebuilds its frontend assets.
Invoked as: python -m bench_cli.tasks.install_app_task <bench_root> <site> <app>
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench_root")
    parser.add_argument("site")
    parser.add_argument("app")
    args = parser.parse_args()

    bench_root = Path(args.bench_root)
    sites_dir = bench_root / "sites"
    bench_bin = str(bench_root / "env" / "bin" / "bench")

    # Step 1: install the app into the site
    print(f"Installing {args.app} into {args.site}...")
    sys.stdout.flush()
    result = subprocess.run(
        [bench_bin, "frappe", "--site", args.site, "install-app", args.app],
        cwd=str(sites_dir),
    )
    if result.returncode != 0:
        sys.exit(result.returncode)

    # Step 2: install JS deps and build assets (app root and frontend separately)
    from bench_cli.tasks.build_assets import build_app_assets
    build_app_assets(bench_root, args.app)


if __name__ == "__main__":
    main()
