import os
import shutil


def new_site_failure_callback(meta: dict):
    """Cleanup site from the directory to ensure reader picksup correct sites"""
    site_name = meta["command_argv"][4]
    site_path = os.path.join(meta["bench_root"], "sites", site_name)
    shutil.rmtree(site_path, ignore_errors=True)
