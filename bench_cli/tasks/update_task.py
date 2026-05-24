"""
Updates all bench apps: git pull + pip install for each app.
Invoked as: python -m bench_cli.tasks.update_task <bench_root>
"""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("bench_root")
    args = parser.parse_args()

    bench_root = Path(args.bench_root)

    from bench_cli.config.bench_config import BenchConfig

    cfg = BenchConfig.from_file(bench_root / "bench.yml")
    pip = str(bench_root / "env" / "bin" / "pip")

    for app in cfg.apps:
        app_path = bench_root / "apps" / app.name
        if not app_path.is_dir():
            print(f"Skipping {app.name}: not cloned")
            sys.stdout.flush()
            continue

        print(f"\n--- Updating {app.name} ---")
        sys.stdout.flush()
        subprocess.run(["git", "pull"], cwd=str(app_path), check=False)

        print(f"Reinstalling {app.name}...")
        sys.stdout.flush()
        subprocess.run([pip, "install", "-e", str(app_path)], check=False)

    print("\nUpdate complete.")


if __name__ == "__main__":
    main()
