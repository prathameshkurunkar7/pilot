from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pilot.exceptions import ConfigError
from pilot.internal.atomic_file import atomic_write_private_text

SYSTEM_PROMPT_FILENAME = ".system-prompt.txt"

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful frappe assistant. Answer as concisely as possible. "
    "Help me fix the migration/task errors that you see in the logs. If you don't "
    'know the answer, just say "I don\'t know". Do not try to make up an answer.'
)


@dataclass
class LLMConfig:
    """Credentials and defaults for the bench's LLM integration.

    Only structured scalars live here (and in bench.toml). The system prompt is
    free text kept in a sidecar file — see `read_system_prompt`.
    """

    provider: str = ""
    api_key: str = ""
    model: str = ""  # blank falls back to the integration's default model
    max_tokens: int = 4096  # hard cap on generated tokens per request

    def validate(self) -> None:
        if self.max_tokens <= 0:
            raise ConfigError("llm.max_tokens must be a positive integer.")


def system_prompt_path(bench_root: Path) -> Path:
    return bench_root / SYSTEM_PROMPT_FILENAME


def read_system_prompt(bench_root: Path) -> str:
    """The bench's system prompt, or the built-in default if none is saved."""
    path = system_prompt_path(bench_root)
    if path.exists():
        return path.read_text(encoding="utf-8")
    return DEFAULT_SYSTEM_PROMPT


def write_system_prompt(bench_root: Path, text: str) -> None:
    atomic_write_private_text(system_prompt_path(bench_root), text)


def clear_system_prompt(bench_root: Path) -> None:
    system_prompt_path(bench_root).unlink(missing_ok=True)
