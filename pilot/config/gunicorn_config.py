from dataclasses import dataclass


@dataclass
class GunicornConfig:
    workers: int = 2
    threads: int = 8
    timeout: int = 120
    worker_class: str = "gthread"
    malloc_arena_max: int = 2  # cap glibc malloc arenas; 0 = unset
    max_requests: int = 2000  # recycle web worker after N requests to release heap; 0 = disabled
    max_requests_jitter: int = 500

    @classmethod
    def from_dict(cls, data: dict) -> "GunicornConfig":
        d = cls()
        return cls(
            workers=data.get("workers", d.workers),
            threads=data.get("threads", d.threads),
            timeout=data.get("timeout", d.timeout),
            worker_class=data.get("worker_class", d.worker_class),
            malloc_arena_max=data.get("malloc_arena_max", d.malloc_arena_max),
            max_requests=data.get("max_requests", d.max_requests),
            max_requests_jitter=data.get("max_requests_jitter", d.max_requests_jitter),
        )
