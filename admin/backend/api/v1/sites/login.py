from __future__ import annotations

import re
import subprocess
from pathlib import Path
from urllib.parse import urlsplit

from flask import current_app, make_response

from pilot.config import BenchConfig
from pilot.utils import normalize_host


def create_site_session(bench_root: Path, site: str) -> str | None:
    python = bench_root / "env" / "bin" / "python"
    program = (
        "import sys, frappe\n"
        "from frappe.auth import CookieManager, LoginManager\n"
        "frappe.init(site=sys.argv[1], sites_path='.')\n"
        "frappe.connect()\n"
        "frappe.utils.set_request(path='/')\n"
        "frappe.local.cookie_manager = CookieManager()\n"
        "frappe.local.login_manager = LoginManager()\n"
        "frappe.local.login_manager.login_as('Administrator')\n"
        "frappe.db.commit()\n"
        "sys.stdout.write(frappe.session.sid)\n"
    )
    result = subprocess.run(
        [str(python), "-c", program, site],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=str(bench_root / "sites"),
    )
    if result.returncode != 0:
        return None
    lines = [line.strip() for line in (result.stdout or "").splitlines() if line.strip()]
    sid = lines[-1] if lines else ""
    return sid if re.fullmatch(r"[A-Za-z0-9._-]+", sid) else None


def login_redirect_url(config: BenchConfig, site: str, site_config: dict) -> str:
    host = primary_host(site, site_config)
    if not config.production.enabled:
        return origin("http", host, config.http_port) + "/desk"

    proxy_tls = current_app.config["SESSION_COOKIE_SECURE"] and not config.admin.tls
    secure = proxy_tls or (config.admin.tls and bool(site_config.get("ssl")))
    scheme = "https" if secure else "http"
    port = 443 if proxy_tls else (config.nginx.https_port if secure else config.nginx.http_port)
    return origin(scheme, host, port) + "/desk"


def primary_host(site: str, site_config: dict) -> str:
    candidates = {normalize_host(site)}
    for entry in site_config.get("domains") or []:
        domain = entry.get("domain") if isinstance(entry, dict) else entry
        if isinstance(domain, str):
            candidates.add(normalize_host(domain))
    host_name = site_config.get("host_name")
    if isinstance(host_name, str) and host_name.strip():
        parsed = urlsplit(host_name if "://" in host_name else f"//{host_name}")
        primary = normalize_host(parsed.hostname or "")
        if primary in candidates:
            return primary
    return normalize_host(site)


def origin(scheme: str, host: str, port: int) -> str:
    default_port = 443 if scheme == "https" else 80
    suffix = "" if port == default_port else f":{port}"
    return f"{scheme}://{host}{suffix}"


def no_store(response):
    response = make_response(response)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
