"""One LLM client for every provider (LiteLLM), with fallback, retries, cost and tracing."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from typing import Any

import litellm

from core.config import settings

litellm.drop_params = True  # ignore params a provider doesn't support
if settings().langfuse_public_key:
    litellm.success_callback = ["langfuse"]
    litellm.failure_callback = ["langfuse"]


@dataclass
class Usage:
    calls: int = 0
    tokens: int = 0
    cost_inr: float = 0.0
    models: list[str] = field(default_factory=list)

    def add(self, response: Any) -> None:
        self.calls += 1
        self.tokens += getattr(getattr(response, "usage", None), "total_tokens", 0) or 0
        with contextlib.suppress(Exception):  # unknown model pricing
            self.cost_inr += litellm.completion_cost(completion_response=response) * settings().usd_inr
        self.models.append(getattr(response, "model", "?"))


def complete(messages: list[dict[str, Any]], *, model: str | None = None,
             tools: list[dict[str, Any]] | None = None, usage: Usage | None = None,
             json_mode: bool = False, metadata: dict[str, Any] | None = None) -> Any:
    cfg = settings()
    kwargs: dict[str, Any] = {
        "model": model or cfg.main_model,
        "messages": messages,
        "fallbacks": [cfg.fallback_model],
        "num_retries": 2,
        "timeout": 20,
        "temperature": 0,
        "metadata": metadata or {},
    }
    if tools:
        kwargs["tools"] = tools
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}
    response = litellm.completion(**kwargs)
    if usage is not None:
        usage.add(response)
    return response
