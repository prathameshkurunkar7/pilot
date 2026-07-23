from __future__ import annotations

from pilot.integrations.llm.base import LLMIntegration


class OpenAIIntegration(LLMIntegration):
    """OpenAI models via litellm."""

    provider = "openai"
    default_model = "gpt-4o"
