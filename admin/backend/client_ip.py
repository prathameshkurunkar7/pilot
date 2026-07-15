from __future__ import annotations

import ipaddress

from flask import current_app, request


def client_ip(default: str = "unknown") -> str:
    """Return a forwarded client IP only when the immediate peer is trusted."""
    peer = request.remote_addr or ""
    trusted_peers = current_app.config.get("TRUSTED_PROXY_PEERS", ())
    if peer in trusted_peers:
        forwarded = request.headers.get("X-Real-IP", "")
        try:
            return str(ipaddress.ip_address(forwarded))
        except ValueError:
            pass
    return peer or default
