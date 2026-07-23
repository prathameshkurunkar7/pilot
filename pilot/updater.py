from __future__ import annotations

import json
import shutil
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path

import pilot
from pilot.exceptions import BenchError
from pilot.utils import cli_root, extract_tar_archive

RELEASE_REPO = "frappe/pilot"
_RELEASES_API = f"https://api.github.com/repos/{RELEASE_REPO}/releases?per_page=1"
_TARBALL_ASSET = "pilot.tar.gz"

Progress = Callable[[str], None]


def latest_release() -> dict | None:
    """Newest release as {tag, asset_url, body}, or None. Uses the releases list (prereleases included)."""
    request = urllib.request.Request(
        _RELEASES_API,
        headers={"Accept": "application/vnd.github+json", "User-Agent": "bench-cli"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        releases = json.load(response)
    if not releases:
        return None
    release = releases[0]
    asset_url = next(
        (a.get("browser_download_url") for a in release.get("assets", []) if a.get("name") == _TARBALL_ASSET),
        None,
    )
    return {"tag": release.get("tag_name"), "asset_url": asset_url, "body": release.get("body", "")}


def update_available() -> tuple[bool, str | None]:
    """Return (is_newer_available, latest_tag) by comparing the newest release tag to __version__."""
    release = latest_release()
    if not release or not release["tag"]:
        return False, None
    return release["tag"] != pilot.__version__, release["tag"]


def perform_upgrade(on_progress: Progress = lambda message: None) -> None:
    """Update the bench-cli code in place. Restarting the admin service is the caller's job."""
    if pilot.is_dev_build:
        _upgrade_dev(on_progress)
    else:
        _upgrade_release(on_progress)


def _upgrade_dev(on_progress: Progress) -> None:
    from admin.backend.frontend import ensure_admin_frontend
    from pilot.managers.environment import AdminEnvManager
    from pilot.utils import run_command

    root = cli_root()
    on_progress("Pulling latest bench-cli (dev install)...")
    run_command(["git", "-C", str(root), "pull"], stream_output=True)
    on_progress("Installing admin Python dependencies...")
    AdminEnvManager(root).install_python_deps()
    on_progress("Rebuilding admin frontend...")
    ensure_admin_frontend(on_progress)


def _upgrade_release(on_progress: Progress) -> None:
    from pilot.managers.environment import AdminEnvManager

    release = latest_release()
    if not release or not release["asset_url"]:
        raise BenchError("No downloadable release asset found; cannot update.")
    if release["tag"] == pilot.__version__:
        on_progress(f"Already on the latest version ({pilot.__version__}).")
        return

    root = cli_root()
    on_progress(f"Updating {pilot.__version__} -> {release['tag']}...")
    with tempfile.TemporaryDirectory() as tmp:
        tarball = Path(tmp) / _TARBALL_ASSET
        on_progress("Downloading release...")
        urllib.request.urlretrieve(release["asset_url"], tarball)
        _back_up_install(root, on_progress)
        # ponytail: extract-over overlays new files but does not delete files
        # dropped between versions; acceptable for now, revisit if stale files bite.
        on_progress("Extracting new version...")
        extract_tar_archive(tarball, root)

    on_progress("Installing admin Python dependencies...")
    AdminEnvManager(root).install_python_deps()
    on_progress(f"Updated to {release['tag']}.")


def _back_up_install(root: Path, on_progress: Progress) -> None:
    backup = root.with_name(root.name + ".backup")
    on_progress(f"Backing up current install to {backup}...")
    if backup.exists():
        shutil.rmtree(backup)
    shutil.copytree(
        root,
        backup,
        symlinks=True,
        ignore=shutil.ignore_patterns(
            ".git", "benches", ".admin-venv", ".venv", "node_modules", "__pycache__"
        ),
    )
