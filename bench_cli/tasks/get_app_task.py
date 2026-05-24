"""
Clones an app repo and pip-installs it into the bench virtualenv.
Invoked as: python -m bench_cli.tasks.get_app_task <bench_root> <name> <repo> [--branch <branch>]
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench_root")
    parser.add_argument("name")
    parser.add_argument("repo")
    parser.add_argument("--branch", default="")
    args = parser.parse_args()

    bench_root = Path(args.bench_root)

    from bench_cli.config.app_config import AppConfig
    from bench_cli.config.bench_config import BenchConfig
    from bench_cli.core.app import App
    from bench_cli.core.bench import Bench
    from bench_cli.managers.python_env_manager import PythonEnvManager

    cfg = BenchConfig.from_file(bench_root / "bench.yml")
    bench = Bench(cfg, bench_root)
    app_cfg = AppConfig(name=args.name, repo=args.repo, branch=args.branch or "main")
    app = App(app_cfg, bench)

    if app.is_cloned:
        print(f"'{args.name}' is already cloned at {app.path}. Skipping clone.")
        sys.stdout.flush()
    else:
        print(f"Cloning {args.name} from {args.repo}...")
        sys.stdout.flush()
        app.clone()

    print(f"Installing {args.name}...")
    sys.stdout.flush()
    PythonEnvManager(bench).install_app(app)

    apps_txt = bench.sites_path / "apps.txt"
    existing = apps_txt.read_text().splitlines() if apps_txt.exists() else []
    if args.name not in existing:
        apps_txt.write_text("\n".join(existing + [args.name]) + "\n")

    from bench_cli.tasks.build_assets import build_app_assets
    build_app_assets(bench_root, args.name)

    print(f"\n'{args.name}' installed successfully.")


if __name__ == "__main__":
    main()
