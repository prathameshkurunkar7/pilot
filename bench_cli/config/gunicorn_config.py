from dataclasses import dataclass


@dataclass
class GunicornConfig:
    workers: int = 4
    threads: int = 4
    timeout: int = 120
    worker_class: str = "sync"
    malloc_arena_max: int = 2  # MALLOC_ARENA_MAX for Python procs; 0/absent = unset
    malloc_trim_requests: int = 100  # malloc_trim(0) after N requests; 0 = disable
    malloc_trim_interval: int = 300  # malloc_trim(0) after N seconds; 0 = disable
