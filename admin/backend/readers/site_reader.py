from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class SiteInfo:
    name: str
    exists: bool
    db_name: str
    db_host: str
    installed_apps: list[str]
    site_config: dict


class SiteReader:
    def __init__(self, bench_root: Path) -> None:
        self._bench_root = bench_root

    def read_all(self) -> list[SiteInfo]:
        sites_path = self._bench_root / "sites"
        if not sites_path.is_dir():
            return []
        return [self._read_site(d.name) for d in sorted(sites_path.iterdir()) if d.is_dir() and (d / "site_config.json").exists()]

    def read_one(self, site_name: str) -> SiteInfo:
        return self._read_site(site_name)

    def _read_site(self, site_name: str) -> SiteInfo:
        site_config_path = self._bench_root / "sites" / site_name / "site_config.json"
        exists = site_config_path.exists()
        site_config: dict = {}

        if exists:
            try:
                site_config = json.loads(site_config_path.read_text())
            except (json.JSONDecodeError, OSError):
                site_config = {}

        db_name = site_config.get("db_name", "")
        db_host = site_config.get("db_host", "localhost")
        installed_apps = self._list_apps(site_name) if exists else []

        return SiteInfo(
            name=site_name,
            exists=exists,
            db_name=db_name,
            db_host=db_host,
            installed_apps=installed_apps,
            site_config=site_config,
        )

    def _list_apps(self, site_name: str) -> list[str]:
        apps = self._list_apps_via_mysql(site_name)
        if apps is not None:
            return apps
        return self._list_apps_via_frappe(site_name)

    def _list_apps_via_mysql(self, site_name: str) -> list[str] | None:
        site_config_path = self._bench_root / "sites" / site_name / "site_config.json"
        try:
            config = json.loads(site_config_path.read_text())
            db_name = config.get("db_name", "")
            db_password = config.get("db_password", "")
            db_host = config.get("db_host", "127.0.0.1")
            db_port = str(config.get("db_port", 3306))
            if not db_name or not db_password:
                return None
            result = subprocess.run(
                [
                    "mysql",
                    f"-u{db_name}",
                    f"-p{db_password}",
                    f"-h{db_host}",
                    f"-P{db_port}",
                    "--batch",
                    "--skip-column-names",
                    db_name,
                    "-e",
                    "SELECT app_name FROM `tabInstalled Applications` ORDER BY idx",
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode != 0:
                return None
            return [line.strip() for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            return None

    def _list_apps_via_frappe(self, site_name: str) -> list[str]:
        python = str(self._bench_root / "env" / "bin" / "python")
        sites_dir = str(self._bench_root / "sites")
        try:
            result = subprocess.run(
                [python, "-m", "frappe.utils.bench_helper", "frappe", "--site", site_name, "list-apps"],
                cwd=sites_dir,
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode != 0:
                return []
            apps = []
            for line in result.stdout.splitlines():
                line = line.strip()
                if line:
                    app_name = line.split()[0]
                    if app_name:
                        apps.append(app_name)
            return apps
        except Exception:
            return []
