from __future__ import annotations

import os
import subprocess
from pathlib import Path

from flask import url_for

from admin.backend.api.responses import created_response, error_response
from admin.backend.api.v1.benches_support import bench_resource, target_bench_dir
from admin.backend.providers.bench import BenchProvider
from pilot.config.toml_store import BenchTomlStore
from pilot.core.bench import Bench
from pilot.exceptions import BenchAlreadyExistsError, BenchError
from pilot.utils import cli_root


def create_bench_locked(
    bench_root: Path,
    name: str,
    process_manager: str,
    db_type: str,
    admin_domain: str,
    admin_tls: bool | None,
):
    from pilot.core.domains import DomainRouteProvider
    from pilot.utils import host_owner, matches_wildcard, normalize_host

    try:
        new_dir = target_bench_dir(bench_root, name)
    except ValueError:
        return error_response(
            "bench_already_exists",
            f"Bench '{name}' already exists.",
            409,
        )
    owner = host_owner(new_dir, admin_domain)
    if owner:
        return error_response(
            "admin_domain_conflict",
            f"Admin domain '{admin_domain}' is already used by bench '{owner}'.",
            409,
        )
    if normalize_host(admin_domain) == normalize_host(name):
        return error_response(
            "invalid_admin_domain",
            "Admin domain must differ from the bench/site name.",
            422,
        )

    patterns = DomainRouteProvider.wildcard_domains()
    if patterns and not matches_wildcard(admin_domain, patterns):
        return error_response(
            "invalid_admin_domain",
            f"Admin domain must match one of: {', '.join(patterns)}.",
            422,
        )

    production_parent = BenchProvider(bench_root).is_production
    if production_parent:
        from pilot.managers.platform import has_passwordless_sudo

        if not has_passwordless_sudo():
            return error_response(
                "privileged_operation_unavailable",
                "Production bench creation requires non-interactive system privileges.",
                409,
            )

    try:
        Bench.create_at(
            new_dir,
            name,
            process_manager=process_manager,
            admin_domain=admin_domain,
            admin_tls=admin_tls,
            db_type=db_type,
        )
    except BenchAlreadyExistsError:
        return error_response(
            "bench_already_exists",
            f"Bench '{name}' already exists.",
            409,
        )
    except BenchError as exc:
        return error_response("invalid_bench", str(exc), 422)

    new_toml = BenchTomlStore.for_bench(new_dir).read_raw()
    new_port = new_toml["admin"]["port"]

    if production_parent:
        return _start_production_setup_wizard(new_dir, name, admin_domain)
    return _start_standalone_setup_wizard(new_dir, name, new_port)


def _start_production_setup_wizard(new_dir: Path, name: str, admin_domain: str):
    from pilot.core.domains import DomainRouteProvider

    try:
        from pilot.managers.nginx import NginxManager
        from pilot.managers.platform import noninteractive_privileges

        with noninteractive_privileges():
            bench = Bench(BenchTomlStore.for_bench(new_dir).read(), new_dir)
            DomainRouteProvider(bench).register(admin_domain, admin_domain)
            pm = _process_manager(bench)
            pm.start_admin()
            nginx = NginxManager(bench)
            nginx.generate_config()
            nginx.install_config()
            server_ip = DomainRouteProvider._server_ip()
    except Exception:
        return error_response(
            "bench_start_failed",
            "The bench was created but its Admin could not be started.",
            500,
            {"created": True, "name": name},
        )
    return created_response(
        {
            **bench_resource(new_dir),
            "wizard_at_domain": True,
            "scheme": "http",
            "server_ip": server_ip,
        },
        url_for("benches.get_bench", name=name),
    )


def _process_manager(bench: Bench):
    from pilot.managers.processes.base import ManagedProcessManager

    configured_pm = bench.config.production.process_manager
    manager_type: type[ManagedProcessManager]
    if configured_pm == "systemd":
        from pilot.managers.processes.systemd import SystemdProcessManager as manager_type
    else:
        from pilot.managers.processes.supervisor import SupervisorProcessManager as manager_type
    return manager_type(bench)


def _start_standalone_setup_wizard(new_dir: Path, name: str, new_port: int):
    root = cli_root()
    spawn_env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("WERKZEUG_") and not key.startswith("BENCH_ADMIN_")
    }
    spawn_env["PYTHONPATH"] = str(root)
    try:
        subprocess.Popen(
            [
                str(root / ".admin-venv" / "bin" / "python"),
                "-m",
                "admin.backend.run_server",
                "--bench-root",
                str(new_dir),
                "--port",
                str(new_port),
                "--timeout",
                "7200",
                "--wizard",
            ],
            cwd=str(root),
            env=spawn_env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return error_response(
            "bench_start_failed",
            "The bench was created but its setup server could not be started.",
            500,
            {"created": True, "name": name},
        )
    return created_response(
        {
            **bench_resource(new_dir),
            "wizard_at_domain": False,
        },
        url_for("benches.get_bench", name=name),
    )
