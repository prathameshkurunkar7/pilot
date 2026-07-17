from dataclasses import dataclass, field


@dataclass
class WorkerGroup:
    """One worker group: spawn ``count`` workers listening to ``queues``."""

    queues: list[str]
    count: int


@dataclass
class WorkerConfig:
    groups: list[WorkerGroup] = field(
        default_factory=lambda: [
            WorkerGroup(queues=["default", "short", "long"], count=1),
        ]
    )

    @classmethod
    def from_dict(cls, data: list) -> "WorkerConfig":
        # [[workers]] array-of-tables: each group lists queues and a count.
        if not isinstance(data, list) or not data:
            return cls()
        groups = [
            WorkerGroup(
                queues=entry.get("queues", [entry.get("queue", "default")]),
                count=entry.get("count", 1),
            )
            for entry in data
        ]
        return cls(groups=groups)
