from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from admin.backend.auth import require_scope

from pilot.core.central_client import CentralClient, CentralClientError

site_name = lambda kw: kw["name"]

# Transparent, allowlisted proxy for a site's calls to Central. The site reaches it at
# `sites/<site>/central/<central.method.path>`; the pilot forwards the call to Central with
# its X-Pilot-Token, so no team/asset ids travel from the site — Central resolves them from
# the credential. The allowlist bounds what a site can reach to Central's pilot-facing
# namespaces: the pilot stays a dumb but bounded forwarder, and Central independently
# enforces @pilot_credential_auth on every method. Adding a Central method needs no change
# here as long as it lives under an allowlisted namespace.
central_proxy_bp = Blueprint("central_proxy", __name__)

# A site may reach Central's billing facade (a namespace) and the heartbeat probe (exact).
# `config`/`enroll` are deliberately excluded: those are the pilot's own boot-time calls to
# Central, not something a site should trigger.
_ALLOWED_PREFIXES = ("central.billing.api.billing_api.",)
_ALLOWED_EXACT = frozenset({"central.api.pilot.heartbeat"})


def _is_allowed(method_path: str) -> bool:
    return method_path in _ALLOWED_EXACT or any(method_path.startswith(p) for p in _ALLOWED_PREFIXES)


def _central() -> CentralClient:
    from pilot.config.toml_store import BenchTomlStore
    from pilot.core.bench import Bench

    bench_root = Path(current_app.config["BENCH_ROOT"])
    bench = Bench(BenchTomlStore.for_bench(bench_root).read(), bench_root)
    return CentralClient(bench)


@central_proxy_bp.route("/<name>/central/<path:method_path>", methods=["GET", "POST"])
@require_scope(site_name)
def proxy(name: str, method_path: str):
    if not _is_allowed(method_path):
        return jsonify({"error": f"Central method '{method_path}' is not permitted."}), 403
    data = request.get_json(silent=True) if request.method == "POST" else None
    try:
        return jsonify(_central().forward(method_path, request.method, data))
    except CentralClientError as exc:
        return jsonify({"error": str(exc)}), 502
