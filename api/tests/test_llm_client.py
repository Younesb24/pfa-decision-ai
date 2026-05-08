"""
Tests for the unified LLM client provider resolution.
Does NOT hit a real LLM — those tests are marked `llm` and skipped in CI.
"""

import llm_client
import pytest


def test_no_provider_when_no_keys(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert llm_client.get_provider() == "none"
    assert llm_client.is_available() is False


def test_anthropic_preferred_when_both_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "fake-anthropic")
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    assert llm_client.get_provider() == "anthropic"
    assert llm_client.is_available() is True


def test_openai_used_when_only_openai_set(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-openai")
    assert llm_client.get_provider() == "openai"


def test_complete_raises_when_no_provider(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="No LLM provider"):
        llm_client.complete(system="s", user="u")
