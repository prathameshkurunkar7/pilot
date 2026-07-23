from __future__ import annotations

from pilot.integrations.llm.base import LLMIntegration


class AnthropicIntegration(LLMIntegration):
    """Anthropic models via litellm."""

    provider = "anthropic"
    default_model = "claude-opus-4-8"
