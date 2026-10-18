"""Cheap, deterministic input checks. Real protection is in the tool layer + RLS; this adds a
signal for traces and the red-team evals."""

import re

MAX_INPUT_CHARS = 2000
INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)",
    r"(reveal|show|print|repeat) (your |the )?(system )?prompt",
    r"you are now", r"developer mode", r"\bDAN\b", r"act as (an? )?(admin|owner|root)",
    r"pretend (to be|you are)", r"disregard (your|the) (rules|instructions)",
    r"base64", r"<\s*/?\s*system\s*>",
]
_RX = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)


def check(text: str) -> tuple[str, list[str]]:
    """Returns (possibly truncated text, flags)."""
    flags = []
    if len(text) > MAX_INPUT_CHARS:
        text = text[:MAX_INPUT_CHARS]
        flags.append("truncated")
    if _RX.search(text):
        flags.append("possible_injection")
    return text, flags
