"""LLM client.

Unified wrapper.

CLAUDE.md locks the stack to Anthropic Claude. This module preferentially uses
Anthropic if ANTHROPIC_API_KEY is set, and falls back to OpenAI GPT-4o if only
OPENAI_API_KEY is present. The fallback exists so the project keeps running for
contributors who only have one of the two providers configured; it is not the
intended production path.

Usage:
    from llm_client import complete, get_provider

    text = complete(
        system="You are an analyst.",
        user="Summarize: ...",
        max_tokens=800,
    )
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

Provider = Literal["anthropic", "openai", "none"]

_ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250929")
_OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")


def _build_http_client():
    """Optional httpx client for environments behind a TLS-intercepting proxy
    (Zscaler / corporate AV). Two opt-in env knobs, neither set by default:

      LLM_CA_BUNDLE=/path/to/corporate-root.pem
          Preferred. Real cert verification, just against your corporate CA.
      LLM_INSECURE_TLS=1
          Last resort. Skips verification entirely. Local-dev only — never
          commit a .env that sets this without a comment explaining why.

    Returns None when neither is set, so the SDK uses its built-in defaults.
    """
    ca_bundle = os.getenv("LLM_CA_BUNDLE")
    insecure = os.getenv("LLM_INSECURE_TLS", "").lower() in ("1", "true", "yes")
    if not ca_bundle and not insecure:
        return None

    try:
        import httpx
    except ImportError:
        return None

    if ca_bundle:
        return httpx.Client(verify=ca_bundle, timeout=60.0)
    return httpx.Client(verify=False, timeout=60.0)


@dataclass(frozen=True)
class LLMResult:
    text: str
    provider: Provider
    model: str


def get_provider() -> Provider:
    """Which provider will `complete()` use? Resolves env at call time."""
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    return "none"


def is_available() -> bool:
    return get_provider() != "none"


def complete(
    *,
    system: str,
    user: str,
    max_tokens: int = 800,
    temperature: float = 0.4,
) -> LLMResult:
    """
    Single-turn completion. Raises RuntimeError if no provider is configured —
    callers should check `is_available()` first if they want a graceful fallback.
    """
    provider = get_provider()

    if provider == "anthropic":
        from anthropic import Anthropic

        # Only pass http_client when explicitly overridden; older SDK versions
        # mis-handle the None case.
        _http = _build_http_client()
        client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], **({"http_client": _http} if _http else {}))
        msg = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Anthropic returns a list of content blocks; we only ask for text.
        text = "".join(block.text for block in msg.content if getattr(block, "type", None) == "text")
        return LLMResult(text=text.strip(), provider="anthropic", model=_ANTHROPIC_MODEL)

    if provider == "openai":
        from openai import OpenAI

        _http = _build_http_client()
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"], **({"http_client": _http} if _http else {}))
        rsp = client.chat.completions.create(
            model=_OPENAI_MODEL,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = rsp.choices[0].message.content or ""
        return LLMResult(text=text.strip(), provider="openai", model=_OPENAI_MODEL)

    raise RuntimeError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY (preferred) or OPENAI_API_KEY."
    )
