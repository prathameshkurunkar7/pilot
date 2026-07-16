from __future__ import annotations

from pathlib import Path


def read_tail_text(path: Path, min_lines: int, block_size: int = 65536) -> str:
    """Read only as much of *path*'s end as needed to contain at least
    ``min_lines`` newlines, doubling the window until enough is found — so
    scanning for a bounded number of trailing lines never touches a large
    file's full size."""
    size = path.stat().st_size
    read_size = min(block_size, size)
    with path.open("rb") as handle:
        while True:
            handle.seek(size - read_size)
            chunk = handle.read(read_size)
            if read_size >= size or chunk.count(b"\n") >= min_lines:
                return chunk.decode(errors="replace")
            read_size = min(read_size * 2, size)
