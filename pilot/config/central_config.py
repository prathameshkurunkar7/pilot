from dataclasses import dataclass


@dataclass
class CentralConfig:
    endpoint: str = ""
    auth_token: str = ""
    # Transient first-boot seed: a single-use token Central minted at VM-create. The pilot
    # exchanges it for `auth_token` (+ JWKS config) on first boot, then it is cleared.
    bootstrap_token: str = ""
