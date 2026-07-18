"""Central integration: the pilot's HTTP client to the Central control plane and its
first-boot enrollment. Public surface re-exported here so callers do
`from pilot.integrations.central import ...` rather than reaching into client/bootstrap.
"""

from __future__ import annotations

from pilot.integrations.central.bootstrap import (
    default_seed_path,
    enroll_if_needed,
    seed,
    seed_from_metadata,
)
from pilot.integrations.central.client import CentralClient, CentralClientError

__all__ = [
    "CentralClient",
    "CentralClientError",
    "default_seed_path",
    "enroll_if_needed",
    "seed",
    "seed_from_metadata",
]
