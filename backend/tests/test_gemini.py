"""Gemini free-tier provider: configuration, key/model gating, and zero-cost pricing.

These are offline checks — no network call is made. They confirm FINN can route research
through Google's free tier when a key is present, and that it degrades (ModelUnavailable)
rather than breaking when the key or model is wrong.
"""
from dataclasses import replace

import pytest

from finn.config import get_settings
from finn.llm import GeminiClient, ModelUnavailable, create_model_client, model_prices


def test_config_selects_gemini(monkeypatch):
    monkeypatch.setenv("FINN_MODEL_PROVIDER", "gemini")
    monkeypatch.setenv("GEMINI_API_KEY", "test-free-key")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")
    monkeypatch.delenv("FINN_MODEL_PRIMARY", raising=False)
    s = get_settings()
    assert s.model_provider == "gemini"
    assert s.model_configured is True
    assert s.model_api_key_env == "GEMINI_API_KEY"
    # Default model is gemini unless the environment/.env explicitly overrides it.
    assert s.model_primary.startswith("gemini-") or "FINN_MODEL_PRIMARY" in __import__("os").environ


def test_gemini_free_tier_is_zero_cost():
    assert model_prices("gemini-2.0-flash") == (0.0, 0.0)
    assert model_prices("gemini-2.5-flash") == (0.0, 0.0)


def test_gemini_client_requires_key(env):
    _, store, _, _ = env
    s = replace(get_settings(), gemini_api_key=None, model_provider="gemini")
    client = create_model_client(s, store)
    assert isinstance(client, GeminiClient)
    with pytest.raises(ModelUnavailable):
        client.generate(job_id=None, model="gemini-2.0-flash", effort="low", system="s", user="u",
                        schema={"type": "object"}, schema_name="t")


def test_gemini_client_rejects_foreign_model(env):
    _, store, _, _ = env
    s = replace(get_settings(), gemini_api_key="test-free-key", model_provider="gemini")
    client = create_model_client(s, store)
    with pytest.raises(ModelUnavailable):
        client.generate(job_id=None, model="claude-haiku-5-5", effort="low", system="s", user="u",
                        schema={"type": "object"}, schema_name="t")
