from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pilot.exceptions import ConfigError


@dataclass
class LLMConfig:
    """Credentials and defaults for the bench's LLM integration."""

    provider: str = ""
    api_key: str = ""
    model: str = ""  # blank falls back to the integration's default model
    max_tokens: int = 4096  # hard cap on generated tokens per request
    system_prompt_path: str = ""  # relative to the bench directory

    def validate(self) -> None:
        if self.max_tokens <= 0:
            raise ConfigError("llm.max_tokens must be a positive integer.")
        self._validate_system_prompt_path()

    def _validate_system_prompt_path(self) -> None:
        path = self.system_prompt_path.strip()
        if not path:
            return
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            raise ConfigError(
                "llm.system_prompt_path must be a relative path inside the bench directory."
            )

    def resolve_system_prompt_path(self, bench_root: Path) -> Path | None:
        """Absolute path to the system prompt file, or None if unset."""
        if not self.system_prompt_path.strip():
            return None
        return bench_root / self.system_prompt_path.strip()
