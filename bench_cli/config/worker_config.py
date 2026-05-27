from dataclasses import dataclass, field


@dataclass
class CustomWorkerEntry:
    queue: str
    count: int
    timeout: int = 300


@dataclass
class WorkerConfig:
    default_count: int = 2
    short_count: int = 1
    long_count: int = 1
    custom: list[CustomWorkerEntry] = field(default_factory=list)
