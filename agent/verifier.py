"""Grounding check: every money amount and decimal number in the answer must appear in some tool
output. Catches the classic failure where the model 'helpfully' recomputes or invents a figure."""

import re
from decimal import Decimal, InvalidOperation
from typing import Any

MONEY = re.compile(r"₹\s?-?[\d,]+(?:\.\d+)?|(?:rs\.?|inr)\s?[\d,]+(?:\.\d+)?", re.IGNORECASE)
DECIMAL = re.compile(r"(?<![\d.])\d+\.\d+(?![\d.])")


def _norm(token: str) -> Decimal | None:
    digits = re.sub(r"[^\d.\-]", "", token.replace(",", ""))
    try:
        return Decimal(digits).normalize() if digits not in {"", "-", "."} else None
    except InvalidOperation:
        return None


def _numbers_in(text: str) -> set[Decimal]:
    found = {_norm(m.group(0)) for m in MONEY.finditer(text)}
    found |= {_norm(m.group(0)) for m in DECIMAL.finditer(text)}
    return {abs(n) for n in found if n is not None}


def _flatten(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(_flatten(v) for v in value)
    return str(value)


def ungrounded_numbers(answer: str, tool_outputs: list[Any]) -> list[str]:
    """Numbers stated in the answer that no tool returned (dates/times are ignored)."""
    evidence_text = " ".join(_flatten(o) for o in tool_outputs)
    evidence = _numbers_in(evidence_text)
    evidence |= {abs(n) for n in (_norm(t) for t in re.findall(r"-?\d[\d,]*\.?\d*", evidence_text))
                 if n is not None}
    return sorted(format(n, "f") for n in _numbers_in(answer) - evidence)
