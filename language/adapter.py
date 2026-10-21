"""The one door every model call goes through (architecture v3 section 34).

    8-second timeout; at most two retries with jittered backoff for transient errors;
    a circuit breaker that disables language shortcuts after repeated failures;
    a cap on concurrent calls.

When the provider fails, generation, repair, editing and employee management keep working; only the
language shortcuts report "unavailable". Model output is untrusted: callers validate it with Pydantic
before using it, and nothing a model says is ever executed directly (section 33).
"""

from __future__ import annotations

import json
import random
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

TIMEOUT_SECONDS = 8.0
MAX_RETRIES = 2
BREAKER_THRESHOLD = 5  # consecutive failures that open the breaker
BREAKER_COOLDOWN_SECONDS = 60.0
MAX_CONCURRENT = 4


class LanguageUnavailable(Exception):
    """Language shortcuts are off right now; the form path still works."""


class Model(Protocol):
    def complete_json(self, system: str, user: str) -> dict[str, Any]: ...


@dataclass
class Breaker:
    threshold: int = BREAKER_THRESHOLD
    cooldown: float = BREAKER_COOLDOWN_SECONDS
    clock: Callable[[], float] = time.monotonic
    failures: int = 0
    opened_at: float | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def allow(self) -> bool:
        with self.lock:
            if self.opened_at is None:
                return True
            if self.clock() - self.opened_at >= self.cooldown:  # half-open: let one call try
                self.opened_at = None
                self.failures = self.threshold - 1
                return True
            return False

    def success(self) -> None:
        with self.lock:
            self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        with self.lock:
            self.failures += 1
            if self.failures >= self.threshold:
                self.opened_at = self.clock()


class Transient(Exception):
    """A failure worth retrying (timeouts, rate limits, 5xx)."""


class Guarded:
    """Wraps a raw model call with the v3 section 34 policy."""

    def __init__(
        self,
        call: Callable[[str, str], dict[str, Any]],
        *,
        breaker: Breaker | None = None,
        max_concurrent: int = MAX_CONCURRENT,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._call = call
        self.breaker = breaker or Breaker()
        self._slots = threading.BoundedSemaphore(max_concurrent)
        self._sleep = sleep

    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        if not self.breaker.allow():
            raise LanguageUnavailable("Language shortcuts are paused after repeated provider failures.")
        if not self._slots.acquire(timeout=2.0):
            raise LanguageUnavailable("Too many language requests at once. Use the form or try again.")
        try:
            for attempt in range(MAX_RETRIES + 1):
                try:
                    out = self._call(system, user)
                    self.breaker.success()
                    return out
                except Transient:
                    if attempt == MAX_RETRIES:
                        break
                    self._sleep((0.25 * 2**attempt) * (0.5 + random.random()))
                except Exception:
                    break
            self.breaker.failure()
            raise LanguageUnavailable("The language service is not responding. Use the form.")
        finally:
            self._slots.release()


def litellm_call(model: str) -> Callable[[str, str], dict[str, Any]]:
    """A raw call to a hosted model (LiteLLM model string, e.g. anthropic/claude-haiku-5-5)."""
    import litellm

    names = (
        "Timeout",
        "RateLimitError",
        "APIConnectionError",
        "ServiceUnavailableError",
        "InternalServerError",
    )
    transient: tuple[type[BaseException], ...] = tuple(
        getattr(litellm, n) for n in names if hasattr(litellm, n)
    )

    def call(system: str, user: str) -> dict[str, Any]:
        try:
            response = litellm.completion(
                model=model,
                messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                timeout=TIMEOUT_SECONDS,
                temperature=0,
                response_format={"type": "json_object"},
                num_retries=0,  # retries are ours, with jitter and the breaker
            )
        except transient as exc:
            raise Transient(str(exc)) from exc
        text = response.choices[0].message.content or "{}"
        parsed = json.loads(text[text.find("{") : text.rfind("}") + 1] or "{}")
        if not isinstance(parsed, dict):
            raise ValueError("model did not return a JSON object")
        return parsed

    return call


_override: Model | None = None
_default: Guarded | None = None


def use(model: Model | None) -> None:
    """Install a model (tests, evaluations); None restores configuration."""
    global _override
    _override = model


def current() -> Model:
    """The configured model, or LanguageUnavailable when none is configured."""
    global _default
    if _override is not None:
        return _override
    from core.config import settings

    name = settings().language_model
    if not name:
        raise LanguageUnavailable("Language shortcuts are not configured on this deployment. Use the form.")
    if _default is None:
        _default = Guarded(litellm_call(name))
    return _default
