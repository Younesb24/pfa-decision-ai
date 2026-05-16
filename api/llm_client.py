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

import json
import os
from dataclasses import dataclass, field
from typing import Any, Literal

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


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict


@dataclass
class ToolCallResult:
    """Returned by complete_with_tools. Either text (loop done) or tool_calls."""

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    provider: Provider = "none"
    model: str = ""


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


# ── Tool-use helpers ───────────────────────────────────────────────────────────


def _to_anthropic_tools(tools: list[dict]) -> list[dict]:
    """Convert neutral-format schemas to Anthropic tool format (input_schema key)."""
    result = []
    for t in tools:
        result.append({
            "name": t["name"],
            "description": t.get("description", ""),
            "input_schema": t.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _to_openai_tools(tools: list[dict]) -> list[dict]:
    """Convert neutral-format schemas to OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            },
        }
        for t in tools
    ]


def _msgs_to_anthropic(messages: list[dict]) -> list[dict]:
    """
    Convert OpenAI-style messages to Anthropic format.

    OpenAI unified format used as source of truth:
      user:      {"role":"user", "content":"text"}
      assistant: {"role":"assistant", "content":"text"}
      assistant tool calls: {"role":"assistant","content":None,
                             "tool_calls":[{"id":..,"name":..,"arguments":{}}]}
      tool result: {"role":"tool","tool_call_id":..,"name":..,"content":"..json.."}
    """
    out: list[dict] = []
    i = 0
    while i < len(messages):
        m = messages[i]
        role = m["role"]

        if role == "user":
            out.append({"role": "user", "content": m["content"]})
            i += 1

        elif role == "assistant":
            if m.get("tool_calls"):
                # Anthropic expects one content block per tool_use
                content = [
                    {
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": tc["name"],
                        "input": tc["arguments"],
                    }
                    for tc in m["tool_calls"]
                ]
                out.append({"role": "assistant", "content": content})
                # Collect the following tool result messages into one user turn
                tool_results = []
                i += 1
                while i < len(messages) and messages[i]["role"] == "tool":
                    tr = messages[i]
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tr["tool_call_id"],
                        "content": tr["content"],
                    })
                    i += 1
                if tool_results:
                    out.append({"role": "user", "content": tool_results})
            else:
                text = m.get("content") or ""
                out.append({
                    "role": "assistant",
                    "content": [{"type": "text", "text": text}],
                })
                i += 1

        else:
            # skip orphan tool messages (already handled above)
            i += 1

    return out


def complete_with_tools(
    *,
    messages: list[dict],
    tools: list[dict],
    system: str,
    max_tokens: int = 4096,
) -> ToolCallResult:
    """
    Single-step tool-use API call (one LLM turn).

    messages — OpenAI-style history (unified format described in _msgs_to_anthropic).
    tools    — neutral-format tool schemas (TOOL_SCHEMAS from agents/tools.py).

    Returns ToolCallResult with either text (stop) or tool_calls (continue loop).
    Raises RuntimeError when no provider is configured.
    """
    provider = get_provider()

    if provider == "anthropic":
        from anthropic import Anthropic

        _http = _build_http_client()
        client = Anthropic(
            api_key=os.environ["ANTHROPIC_API_KEY"],
            **({"http_client": _http} if _http else {}),
        )
        ant_tools = _to_anthropic_tools(tools)
        ant_messages = _msgs_to_anthropic(messages)

        resp = client.messages.create(
            model=_ANTHROPIC_MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=ant_tools,  # type: ignore[arg-type]
            messages=ant_messages,
        )

        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        for block in resp.content:
            if getattr(block, "type", None) == "tool_use":
                tool_calls.append(ToolCall(
                    id=block.id,
                    name=block.name,
                    arguments=dict(block.input),
                ))
            elif getattr(block, "type", None) == "text":
                text_parts.append(block.text)

        return ToolCallResult(
            text=" ".join(text_parts).strip() or None,
            tool_calls=tool_calls,
            provider="anthropic",
            model=_ANTHROPIC_MODEL,
        )

    if provider == "openai":
        from openai import OpenAI

        _http = _build_http_client()
        client = OpenAI(
            api_key=os.environ["OPENAI_API_KEY"],
            **({"http_client": _http} if _http else {}),
        )
        oai_tools = _to_openai_tools(tools)
        # OpenAI messages use the same format we already have
        oai_messages: list[Any] = [{"role": "system", "content": system}, *messages]

        resp = client.chat.completions.create(
            model=_OPENAI_MODEL,
            max_tokens=max_tokens,
            tools=oai_tools,  # type: ignore[arg-type]
            messages=oai_messages,
        )
        msg = resp.choices[0].message

        if msg.tool_calls:
            tool_calls = []
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except Exception:
                    args = {}
                tool_calls.append(ToolCall(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
            return ToolCallResult(
                text=None,
                tool_calls=tool_calls,
                provider="openai",
                model=_OPENAI_MODEL,
            )

        return ToolCallResult(
            text=(msg.content or "").strip() or None,
            tool_calls=[],
            provider="openai",
            model=_OPENAI_MODEL,
        )

    raise RuntimeError(
        "No LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
    )
