"""Thin Claude wrapper.

Why wrap the SDK at all:
- Notebooks should read like the conceptual flow, not like API plumbing
- One place to add prompt caching, retries, and cost logging later
- Easy to swap model per-call without remembering parameter names

This file intentionally exposes one function, `ask()`, plus `ask_json()`
for structured outputs. Everything else (streaming, tool use) appears in
the hours that introduce those concepts.
"""

from __future__ import annotations

import json
import re
from typing import Any

from anthropic import Anthropic

from kg_tutorial import config

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        config.verify()
        _client = Anthropic(api_key=config.ANTHROPIC_API_KEY)
    return _client


def ask(
    prompt: str,
    *,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.0,
) -> str:
    """One-shot text completion. Returns the model's text output.

    Defaults to deterministic (`temperature=0`) and Sonnet. Pass
    `model=config.MODEL_REASONING` for Opus on hard reasoning calls.
    """
    client = _get_client()
    model = model or config.MODEL_DEFAULT
    kwargs: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    if config.VERBOSE_LLM:
        print(f"[llm] model={model} tokens<={max_tokens} prompt_len={len(prompt)}")

    response = client.messages.create(**kwargs)
    return "".join(block.text for block in response.content if block.type == "text")


def ask_json(prompt: str, **kwargs: Any) -> dict | list:
    """Ask Claude for JSON. Strips markdown fences if present.

    Use this whenever you want a structured answer. We force the model into
    JSON via the prompt suffix rather than using tool-use schema — keeps the
    teaching clear about what's actually happening.
    """
    suffix = (
        "\n\nRespond with valid JSON only. No prose, no markdown fences. "
        "If you must explain, put it inside a JSON field called `reasoning`."
    )
    raw = ask(prompt + suffix, **kwargs)
    # Defensive: some models still wrap in fences
    cleaned = re.sub(r"^```(?:json)?\n?|\n?```$", "", raw.strip(), flags=re.MULTILINE)
    return json.loads(cleaned)
