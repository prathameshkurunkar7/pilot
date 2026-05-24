"""
Switches an app to a different git branch, reinstalls it, and rebuilds assets.
Invoked as: python -m bench_cli.tasks.switch_branch_task <bench_root> <app_name> <branch>
"""
import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench_root")
    parser.add_argument("app_name")
    parser.add_argument("branch")
    args = parser.parse_args()

    bench_root = Path(args.bench_root)
    app_path = bench_root / "apps" / args.app_name
    sites_dir = bench_root / "sites"
    bench_bin = str(bench_root / "env" / "bin" / "bench")
    python_bin = str(bench_root / "env" / "bin" / "python")

    from bench_cli.utils import uv_bin

    if not (app_path / ".git").exists():
        print(f"Error: '{args.app_name}' is not cloned at {app_path}")
        sys.exit(1)

    print(f"Fetching all remote branches for {args.app_name}...")
    sys.stdout.flush()
    # Use an explicit refspec so all remote branches are fetched even when the
    # repo was cloned with --single-branch (which limits the fetch refspec to
    # just the cloned branch).
    subprocess.run(
        ["git", "-C", str(app_path), "fetch", "origin",
         "+refs/heads/*:refs/remotes/origin/*"],
        check=False,
    )

    # Abort any in-progress merge/rebase so the working tree is clean
    subprocess.run(["git", "-C", str(app_path), "merge", "--abort"],
                   capture_output=True, check=False)
    subprocess.run(["git", "-C", str(app_path), "rebase", "--abort"],
                   capture_output=True, check=False)

    # Stash any remaining local changes so checkout can proceed
    stash_result = subprocess.run(
        ["git", "-C", str(app_path), "stash", "--include-untracked"],
        capture_output=True, text=True, check=False,
    )
    stashed = "No local changes" not in stash_result.stdout

    print(f"Switching to branch '{args.branch}'...")
    sys.stdout.flush()

    # -B creates the branch if it doesn't exist, or resets it to the given
    # start point if it already exists — either way ends up clean on the branch.
    result = subprocess.run(
        ["git", "-C", str(app_path), "checkout", "-B", args.branch,
         f"origin/{args.branch}"],
        check=False,
    )
    if result.returncode != 0:
        if stashed:
            subprocess.run(["git", "-C", str(app_path), "stash", "pop"], check=False)
        print(f"Error: could not switch to branch '{args.branch}'")
        sys.exit(result.returncode)

    print(f"Reinstalling {args.app_name}...")
    sys.stdout.flush()
    subprocess.run(
        [uv_bin(), "pip", "install", "--python", python_bin, "-e", str(app_path)],
        check=False,
    )

    # Update bench.yml to reflect the new active branch
    import yaml
    bench_yml = bench_root / "bench.yml"
    raw = yaml.safe_load(bench_yml.read_text()) or {}
    for app_entry in raw.get("apps", []):
        if app_entry.get("name") == args.app_name:
            app_entry["branch"] = args.branch
            break
    bench_yml.write_text(
        yaml.dump(raw, default_flow_style=False, allow_unicode=True, sort_keys=False)
    )
    print(f"Updated bench.yml: {args.app_name} -> {args.branch}")
    sys.stdout.flush()

    # Rebuild assets — app root and frontend treated as separate JS projects
    from bench_cli.tasks.build_assets import build_app_assets
    build_app_assets(bench_root, args.app_name)

    print(f"\n'{args.app_name}' switched to '{args.branch}' successfully.")


if __name__ == "__main__":
    main()
