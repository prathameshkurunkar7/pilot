from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from pilot.core.central_client import CentralClientError, _message

if TYPE_CHECKING:
    from pilot.core.bench import Bench

# First-boot enrollment. Atlas seeds only two things at VM-create: the Central endpoint
# and a single-use bootstrap token (see Phase 6 delivery). On first boot the pilot
# exchanges that token for its long-lived credential AND its JWKS trust config in one
# call — so nothing else has to be injected, and a later change to the JWKS URL or
# audience is picked up by re-enrolling rather than re-provisioning.

ENROLL_METHOD = "central.api.pilot.enroll"

# Canonical location a first-boot hook finds the create-time seed at. Atlas drops
# {central_endpoint, bootstrap_token} here from VM metadata (cloud-init / MMDS); the golden
# image's boot unit then runs a bare `bench enroll`, which auto-reads it. On tmpfs (`/run`)
# so the single-use token never survives a reboot. Override with $PILOT_SEED_PATH.
DEFAULT_SEED_PATH = "/run/pilot/central-seed.json"


def default_seed_path() -> str:
    import os

    return os.environ.get("PILOT_SEED_PATH", DEFAULT_SEED_PATH)


def seed_from_metadata(bench: "Bench", path: str) -> bool:
    """Stage a seed that VM create-time metadata (cloud-init / Firecracker MMDS) dropped at
    ``path`` as JSON ``{central_endpoint, bootstrap_token}``. Returns True if a usable seed
    was found. This is the boot-free path: a first-boot hook runs ``bench enroll --seed-file
    <path>`` so the pilot enrols from metadata, with no controller SSHing in post-boot."""
    from pathlib import Path

    source = Path(path)
    if not source.exists():
        return False
    data = json.loads(source.read_text())
    endpoint, token = data.get("central_endpoint"), data.get("bootstrap_token")
    if not endpoint or not token:
        return False
    seed(bench, endpoint, token)
    return True


def seed(bench: "Bench", endpoint: str, bootstrap_token: str) -> None:
    """Write the create-time seed (Central endpoint + single-use bootstrap token) into
    bench.toml ``[central]`` and refresh the in-memory config, so ``enroll_if_needed`` can
    exchange it. This is what Atlas delivers at provision time."""
    from pilot.config.toml_store import BenchTomlStore

    store = BenchTomlStore.for_bench(bench.path)
    config = store.read_raw()
    central = config.setdefault("central", {})
    central["endpoint"] = endpoint
    central["bootstrap_token"] = bootstrap_token
    store.write_raw(config)

    bench.config.central.endpoint = endpoint
    bench.config.central.bootstrap_token = bootstrap_token


def enroll_if_needed(bench: "Bench") -> bool:
    """Idempotent first-boot enrollment.

    Does nothing if the bench already holds a Central ``auth_token``. Otherwise exchanges
    the seeded bootstrap token for this pilot's long-lived credential + JWKS discovery and
    persists both into bench.toml (the credential under ``[central]``, the JWKS trust
    config under ``[admin]``). Returns True if it enrolled, False if already enrolled."""
    central = bench.config.central
    if central.auth_token:
        return False
    if not central.endpoint or not central.bootstrap_token:
        raise CentralClientError(
            "Cannot enrol: central.endpoint / central.bootstrap_token not set in bench.toml"
        )
    result = _enroll(central.endpoint.rstrip("/"), central.bootstrap_token)
    _persist(bench, result)
    return True


def _enroll(endpoint: str, bootstrap_token: str) -> dict[str, Any]:
    """POST the bootstrap token to Central's guest enroll endpoint. No credential is sent —
    the signed, single-use bootstrap token is the only authentication."""
    body = json.dumps({"bootstrap_token": bootstrap_token}).encode()
    request = urllib.request.Request(
        f"{endpoint}/api/method/{ENROLL_METHOD}",
        data=body,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        raise CentralClientError(f"Enrollment rejected: Central returned HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise CentralClientError(f"Cannot reach Central at {endpoint}: {exc.reason}") from exc
    except ValueError as exc:
        raise CentralClientError(f"Central returned a non-JSON enrollment response: {exc}") from exc
    return _message(payload)


def _persist(bench: "Bench", result: dict[str, Any]) -> None:
    """Write the enrolled credential + JWKS trust config into bench.toml and refresh the
    in-memory config. The bootstrap token is dropped — it is single-use and now spent."""
    from pilot.config.toml_store import BenchTomlStore

    missing = [key for key in ("auth_token", "jwks_url", "audience_id") if not result.get(key)]
    if missing:
        raise CentralClientError(f"Enrollment response missing: {', '.join(missing)}")

    store = BenchTomlStore.for_bench(bench.path)
    config = store.read_raw()

    central = config.setdefault("central", {})
    central["endpoint"] = result.get("central_endpoint") or central.get("endpoint", "")
    central["auth_token"] = result["auth_token"]
    central.pop("bootstrap_token", None)

    admin = config.setdefault("admin", {})
    admin["jwks_url"] = result["jwks_url"]
    admin["jwks_audience"] = result["audience_id"]

    store.write_raw(config)

    bench.config.central.endpoint = central["endpoint"]
    bench.config.central.auth_token = central["auth_token"]
    bench.config.central.bootstrap_token = ""
    bench.config.admin.jwks_url = result["jwks_url"]
    bench.config.admin.jwks_audience = result["audience_id"]
