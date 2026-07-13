from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from admin.backend.auth import require_scope

from pilot.core.central_client import CentralClient, CentralClientError

site_name = lambda kw: kw["name"]

# Site-scoped billing routes proxied to Central. Registered under the same
# `/api/sites` prefix as sites_bp, so the site's PilotClient reaches them at
# `sites/<site>/billing/...`. The credential's team + asset are resolved by
# Central from the X-Pilot-Token, so no ids travel from here.
site_billing_bp = Blueprint("site_billing", __name__)


def _central() -> CentralClient:
    from pilot.config.toml_store import BenchTomlStore
    from pilot.core.bench import Bench

    bench_root = Path(current_app.config["BENCH_ROOT"])
    bench = Bench(BenchTomlStore.for_bench(bench_root).read(), bench_root)
    return CentralClient(bench)


def _proxy(call):
    """Run a Central call, turning a client error into the {"error": ...} body the
    site's PilotClient already knows how to surface."""
    try:
        return jsonify(call())
    except CentralClientError as exc:
        return jsonify({"error": str(exc)}), 502


@site_billing_bp.route("/<name>/billing/summary", methods=["GET"])
@require_scope(site_name)
def summary(name: str):
    try:
        billing = _central().billing_summary()
    except CentralClientError as exc:
        return jsonify({"error": str(exc)}), 502
    # Central should return a dict; anything else surfaces as the billing-error shape
    # the other routes use, not a 500 while we index it.
    if not isinstance(billing, dict):
        return jsonify({"error": "Central returned an unexpected billing summary."}), 502
    plan = billing.get("plan")
    billing["usage"] = _usage_meters(plan if isinstance(plan, dict) else {}, current_app.config["BENCH_ROOT"])
    return jsonify(billing)


@site_billing_bp.route("/<name>/billing/plans", methods=["GET"])
@require_scope(site_name)
def plans(name: str):
    return _proxy(lambda: _central().available_plans())


@site_billing_bp.route("/<name>/billing/change-plan", methods=["POST"])
@require_scope(site_name)
def change_plan(name: str):
    plan = ((request.get_json(silent=True) or {}).get("plan") or "").strip()
    if not plan:
        return jsonify({"error": "A plan is required."}), 400
    return _proxy(lambda: _central().change_plan(plan))


@site_billing_bp.route("/<name>/billing/profile", methods=["GET"])
@require_scope(site_name)
def get_profile(name: str):
    return _proxy(lambda: _central().billing_profile())


@site_billing_bp.route("/<name>/billing/profile", methods=["POST"])
@require_scope(site_name)
def save_profile(name: str):
    fields = request.get_json(silent=True) or {}
    return _proxy(lambda: _central().save_billing_profile(fields))


@site_billing_bp.route("/<name>/billing/gateways", methods=["GET"])
@require_scope(site_name)
def payment_gateways(name: str):
    return _proxy(lambda: _central().payment_gateways())


@site_billing_bp.route("/<name>/billing/payment-method", methods=["POST"])
@require_scope(site_name)
def add_payment_method(name: str):
    data = request.get_json(silent=True) or {}
    method_type = (data.get("method_type") or "Card").strip()
    contact = (data.get("contact") or "").strip() or None
    gateway = (data.get("gateway") or "").strip() or None
    return _proxy(lambda: _central().add_payment_method(method_type, contact=contact, gateway=gateway))


@site_billing_bp.route("/<name>/billing/payment-method/confirm", methods=["POST"])
@require_scope(site_name)
def confirm_payment_method(name: str):
    payload = request.get_json(silent=True) or {}
    return _proxy(lambda: _central().confirm_payment_method(payload))


@site_billing_bp.route("/<name>/billing/payment-method/remove", methods=["POST"])
@require_scope(site_name)
def remove_payment_method(name: str):
    method = ((request.get_json(silent=True) or {}).get("payment_method") or "").strip()
    if not method:
        return jsonify({"error": "payment_method is required."}), 400
    return _proxy(lambda: _central().remove_payment_method(method))


@site_billing_bp.route("/<name>/billing/payment-method/checkout", methods=["POST"])
@require_scope(site_name)
def payment_method_checkout(name: str):
    data = request.get_json(silent=True) or {}
    redirect_url = (data.get("redirect_url") or "").strip()
    gateway = (data.get("gateway") or "").strip() or None
    if not redirect_url:
        return jsonify({"error": "redirect_url is required."}), 400
    return _proxy(lambda: _central().create_payment_method_checkout(redirect_url, gateway))


@site_billing_bp.route("/<name>/billing/payment-method/checkout/confirm", methods=["POST"])
@require_scope(site_name)
def payment_method_checkout_confirm(name: str):
    reference = ((request.get_json(silent=True) or {}).get("reference") or "").strip()
    if not reference:
        return jsonify({"error": "reference is required."}), 400
    return _proxy(lambda: _central().confirm_payment_method_checkout(reference))


@site_billing_bp.route("/<name>/billing/reconcile-setup", methods=["POST"])
@require_scope(site_name)
def reconcile_setup(name: str):
    return _proxy(lambda: _central().reconcile_payment_setup())


@site_billing_bp.route("/<name>/billing/topup-checkout", methods=["POST"])
@require_scope(site_name)
def topup_checkout(name: str):
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")
    redirect_url = (data.get("redirect_url") or "").strip()
    if not amount or not redirect_url:
        return jsonify({"error": "amount and redirect_url are required."}), 400
    return _proxy(lambda: _central().create_topup_checkout(amount, redirect_url))


@site_billing_bp.route("/<name>/billing/checkout-status", methods=["POST"])
@require_scope(site_name)
def checkout_status(name: str):
    reference = ((request.get_json(silent=True) or {}).get("reference") or "").strip()
    if not reference:
        return jsonify({"error": "reference is required."}), 400
    return _proxy(lambda: _central().checkout_status(reference))


def _usage_meters(plan: dict, bench_root) -> list[dict]:
    """Live server usage (this bench's VM) labelled with the plan's specs — the
    percentages come from the monitoring daemon's latest system sample, the labels
    from Central's plan. Zeroed until the daemon has written a sample."""
    from admin.backend.readers.monitor_reader import latest_system_metrics

    specs = plan.get("specs") or {}
    metrics = latest_system_metrics(Path(bench_root))
    memory = metrics.get("memory") or {}
    disk = (metrics.get("storage") or {}).get("disk") or {}
    return [
        {"name": "CPU", "percent": round(metrics.get("cpu_percent") or 0), "detail": specs.get("cpu")},
        {"name": "Memory", "percent": round(memory.get("percent") or 0), "detail": specs.get("memory")},
        {"name": "Storage", "percent": round(disk.get("percent") or 0), "detail": specs.get("storage")},
    ]
