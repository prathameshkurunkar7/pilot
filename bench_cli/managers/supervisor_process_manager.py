from __future__ import annotations

import os
from pathlib import Path

from bench_cli.managers.admin_env_manager import AdminEnvManager
from bench_cli.managers.process_manager import ProcessDefinition, ProcessManager, _cli_root
from bench_cli.utils import run_command


class SupervisorProcessManager(ProcessManager):
    """Manages bench processes via supervisord (used in production)."""

    @property
    def supervisor_conf_path(self) -> Path:
        return self.bench.config_path / "supervisor" / f"{self.bench.config.name}.conf"

    @property
    def supervisor_include_dir(self) -> Path:
        return Path("/etc/supervisor/conf.d")

    def generate_config(self) -> None:
        AdminEnvManager(_cli_root()).ensure()
        self.supervisor_conf_path.parent.mkdir(parents=True, exist_ok=True)
        conf = self._render_supervisor_conf()
        self.supervisor_conf_path.write_text(conf)

    def install_config(self) -> None:
        """We don't need to do this at all, we can simply include everything in the supervisord.conf file"""
        symlink = self.supervisor_include_dir / f"{self.bench.config.name}.conf"
        if symlink.exists() or symlink.is_symlink():
            symlink.unlink()
        try:
            os.symlink(self.supervisor_conf_path, symlink)
        except PermissionError:
            print(
                f"Permission denied creating symlink at {symlink}.\n"
                f"Run manually:\n"
                f"  sudo ln -sf {self.supervisor_conf_path} {symlink}\n"
                f"Then reload supervisord:\n"
                f"  sudo supervisorctl reread && sudo supervisorctl update"
            )

    def reload(self) -> None:
        run_command(["supervisorctl", "reread"])
        run_command(["supervisorctl", "update"])

    def start(self) -> None:
        run_command(["supervisorctl", "start", f"{self.bench.config.name}:*"])

    def stop(self) -> None:
        run_command(["supervisorctl", "stop", f"{self.bench.config.name}:*"])

    def restart(self) -> None:
        run_command(["supervisorctl", "restart", f"{self.bench.config.name}:*"])

    def is_running(self) -> bool:
        import subprocess

        result = subprocess.run(
            ["supervisorctl", "status", f"{self.bench.config.name}:*"],
            capture_output=True,
            text=True,
        )
        return "RUNNING" in result.stdout

    def reload_web(self) -> None:
        """Clear the Frappe asset cache in Redis then restart the web worker."""
        import subprocess

        cache_port = self.bench.config.redis.cache_port
        subprocess.run(["redis-cli", "-p", str(cache_port), "del", "assets_json"], capture_output=True)
        if self.is_running():
            print("Restarting web worker to pick up new assets...")
            run_command(["supervisorctl", "restart", f"{self.bench.config.name}:{self.bench.config.name}-web"])

    def _process_definitions(self) -> list[ProcessDefinition]:
        return self._shared_process_definitions()

    def _admin_definition(self, *, dev: bool = False) -> ProcessDefinition:
        return super()._admin_definition(dev=dev)

    def _render_supervisor_conf(self) -> str:
        defs = self._process_definitions()
        program_names = ",".join(f"{self.bench.config.name}-{pd.name.replace('_', '-')}" for pd in defs)
        group = f"[group:{self.bench.config.name}]\nprograms={program_names}\n\n"
        blocks = [self._render_program(pd, pd.name.replace("_", "-")) for pd in defs]
        return group + "".join(blocks)

    def _render_program(self, pd: ProcessDefinition, safe_name: str) -> str:
        import re

        log_dir = self.bench.logs_path
        cmd = pd.command

        # Extract leading VAR=value env assignments
        env_vars: list[str] = []
        while True:
            m = re.match(r"^([A-Z_][A-Z0-9_]*)=(\S+)\s+", cmd)
            if not m:
                break
            env_vars.append(f'{m.group(1)}="{m.group(2)}"')
            cmd = cmd[m.end() :]

        # Extract leading `cd /dir && ` working-directory prefix
        directory = ""
        m2 = re.match(r"^cd\s+(\S+)\s*&&\s*", cmd)
        if m2:
            directory = m2.group(1)
            cmd = cmd[m2.end() :]

        lines = [
            f"[program:{self.bench.config.name}-{safe_name}]",
            f"command={cmd}",
            "autostart=true",
            "autorestart=true",
            f"stdout_logfile={log_dir}/{pd.name}.log",
            f"stderr_logfile={log_dir}/{pd.name}.error.log",
            "user=root",
            "stopasgroup=true",
            "killasgroup=true",
        ]
        if directory:
            lines.insert(2, f"directory={directory}")
        if env_vars:
            lines.insert(2, f"environment={','.join(env_vars)}")
        return "\n".join(lines) + "\n\n"
