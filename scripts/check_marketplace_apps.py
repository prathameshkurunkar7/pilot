#!/usr/bin/env python3
"""
Orchestrates the marketplace app PR check: find which targets changed
(diff_marketplace_apps.py), then run each through run_semgrep.py
(Semgrep scan) and validate_marketplace_app.py (quality checks).
Exits non-zero if any target fails either check.

Run:
    python3 scripts/check_marketplace_apps.py <old-apps.json> <new-apps.json>
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from clone_utils import clone_app
from run_semgrep import run_semgrep
from run_app_validations import AppValidator

DIFF_SCRIPT = Path(__file__).parent / "diff_marketplace_apps.py"


def find_changed_targets(old_path: str, new_path: str) -> list[dict]:
    result = subprocess.run(
        ["python3", str(DIFF_SCRIPT), old_path, new_path],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def check_target(target: dict) -> bool:
    repo, ref, target_type = target["repo"], target["target"], target["target_type"]
    label = f"{target['name']} ({repo}@{ref})"
    print(f"\n=== Checking {label} ===", flush=True)

    with tempfile.TemporaryDirectory() as tmp:
        clone_dir = Path(tmp) / "app"
        try:
            clone_app(repo, ref, target_type, clone_dir)
        except RuntimeError as exc:
            print(f"  FAIL: {exc}")
            return False

        semgrep_passed = run_semgrep(clone_dir, f"{repo}@{ref}")
        validate_passed = AppValidator(repo, ref, target_type).run_on_dir(clone_dir)

    return semgrep_passed and validate_passed


def main() -> None:
    if len(sys.argv) != 3:
        print("Usage: check_marketplace_apps.py <old-apps.json> <new-apps.json>", file=sys.stderr)
        sys.exit(1)

    changed_targets = find_changed_targets(sys.argv[1], sys.argv[2])
    if not changed_targets:
        print("No app code changes detected — nothing to scan.")
        return

    results = {f"{t['name']}@{t['target']}": check_target(t) for t in changed_targets}
    failed = [key for key, passed in results.items() if not passed]

    if failed:
        print(f"\nFAILED: {', '.join(failed)} did not pass the marketplace checks.")
        sys.exit(1)

    print(f"\nAll {len(changed_targets)} changed target(s) passed.")


if __name__ == "__main__":
    main()
