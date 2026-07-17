from dataclasses import dataclass
from typing import Optional


@dataclass
class RedisConfig:
    cache_port: int = 13000
    queue_port: int = 11000
    version: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict) -> "RedisConfig":
        return cls(
            cache_port=data.get("cache_port", 13000),
            queue_port=data.get("queue_port", 11000),
            version=data.get("version"),
        )
