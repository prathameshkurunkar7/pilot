from flask import Blueprint

sites_bp = Blueprint("sites", __name__)

from admin.backend.api.v1.sites import apps, backups, central, configuration, core, domains  # noqa: E402

__all__ = [
    "apps",
    "backups",
    "central",
    "configuration",
    "core",
    "domains",
    "sites_bp",
]
