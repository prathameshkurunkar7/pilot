"""Tests for editing the [llm] config via the admin Settings API."""

from __future__ import annotations

from admin.backend.api.v1.settings import ConfigPatcher, build_settings_response
from pilot.config import BenchConfig


def _config() -> BenchConfig:
    return BenchConfig._from_dict(
        {
            "bench": {"name": "test-bench", "python": "3.14"},
            "apps": [{"name": "frappe", "repo": "https://github.com/frappe/frappe", "branch": "develop"}],
            "mariadb": {"root_password": "root"},
        }
    )


def test_patcher_updates_provider_key_and_defaults() -> None:
    config = _config()

    error = ConfigPatcher(
        config,
        {
            "llm": {
                "provider": "anthropic",
                "api_key": "sk-key",
                "model": "claude-opus-4-8",
                "max_tokens": 2048,
                "system_prompt_path": "./system-prompt",
            }
        },
    ).apply()

    assert error is None
    assert config.llm.provider == "anthropic"
    assert config.llm.api_key == "sk-key"
    assert config.llm.model == "claude-opus-4-8"
    assert config.llm.max_tokens == 2048
    assert config.llm.system_prompt_path == "./system-prompt"


def test_patcher_sets_key_only_when_provided() -> None:
    config = _config()
    config.llm.api_key = "original"

    # blank key is preserved, not cleared (write-only field)
    ConfigPatcher(config, {"llm": {"provider": "openai", "api_key": ""}}).apply()
    assert config.llm.api_key == "original"
    assert config.llm.provider == "openai"


def test_patcher_rejects_unknown_provider() -> None:
    config = _config()
    error = ConfigPatcher(config, {"llm": {"provider": "nope", "api_key": "k"}}).apply()
    assert error is not None
    assert "llm.provider" in error


def test_patcher_rejects_escaping_system_prompt_path() -> None:
    config = _config()
    error = ConfigPatcher(
        config, {"llm": {"provider": "openai", "api_key": "k", "system_prompt_path": "../secrets"}}
    ).apply()
    assert error is not None
    assert "system_prompt_path" in error


def test_patcher_disconnect_resets_llm() -> None:
    config = _config()
    config.llm.provider = "openai"
    config.llm.api_key = "sk-key"

    ConfigPatcher(config, {"llm": {"disconnect": True}}).apply()
    assert config.llm == type(config.llm)()


def test_patcher_ignores_absent_llm_section() -> None:
    config = _config()
    assert ConfigPatcher(config, {}).apply() is None
    assert config.llm == type(config.llm)()


def test_response_exposes_llm_without_secret() -> None:
    config = _config()
    config.llm.provider = "anthropic"
    config.llm.api_key = "sk-secret"
    config.llm.model = "claude-opus-4-8"

    payload = build_settings_response(config)

    assert payload["llm"]["provider"] == "anthropic"
    assert payload["llm"]["api_key_set"] is True
    assert payload["llm"]["model"] == "claude-opus-4-8"
    assert "api_key" not in payload["llm"]
    assert {p["value"] for p in payload["llm_providers"]} == {"anthropic", "openai"}
