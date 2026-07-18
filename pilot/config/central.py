from dataclasses import dataclass


@dataclass
class CentralConfig:
    endpoint: str = ""
    auth_token: str = ""
    # Transient first-boot seed: a single-use token Central minted at VM-create. The pilot
    # exchanges it for `auth_token` (+ JWKS config) on first boot, then it is cleared.
    bootstrap_token: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "CentralConfig":
        return cls(
            endpoint=data.get("endpoint", ""),
            auth_token=data.get("auth_token", ""),
            bootstrap_token=data.get("bootstrap_token", ""),
        )
