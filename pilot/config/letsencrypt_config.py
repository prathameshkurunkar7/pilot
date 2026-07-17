from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class LetsEncryptConfig:
    email: str = ""
    webroot_path: Path = field(default_factory=lambda: Path("/var/www/letsencrypt"))

    @classmethod
    def from_dict(cls, data: dict) -> "LetsEncryptConfig":
        return cls(
            email=data.get("email", ""),
            webroot_path=Path(data.get("webroot_path", "/var/www/letsencrypt")),
        )
