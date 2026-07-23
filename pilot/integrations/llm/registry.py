"""Known LLM providers, for the settings UI and provider validation."""

from __future__ import annotations

from pilot.integrations.llm.anthropic import AnthropicIntegration
from pilot.integrations.llm.base import LLMIntegration
from pilot.integrations.llm.openai import OpenAIIntegration

PROVIDER_LABELS = {
    "anthropic": "Anthropic",
    "openai": "OpenAI",
}

INTEGRATIONS: dict[str, type[LLMIntegration]] = {
    AnthropicIntegration.provider: AnthropicIntegration,
    OpenAIIntegration.provider: OpenAIIntegration,
}


def integration_for(provider: str) -> type[LLMIntegration]:
    """Return the integration class for a provider slug."""
    try:
        return INTEGRATIONS[provider]
    except KeyError as error:
        raise ValueError(f"Unknown LLM provider: {provider!r}") from error
