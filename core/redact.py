"""PII masking for logs, traces and audit rows. Applied before anything leaves the process."""

import re
from typing import Any

PHONE = re.compile(r"(?<!\d)(\+?91[\s-]?)?[6-9]\d{9}(?!\d)")
ACCOUNT = re.compile(r"(?<!\d)\d{11,18}(?!\d)")  # bank account numbers
IFSC = re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b")
SENSITIVE_KEYS = {"phone", "account_number", "ifsc", "pan", "aadhaar", "net_pay", "base_pay"}


def mask_text(text: str) -> str:
    text = PHONE.sub(lambda m: m.group(0)[:-10] + "XXXXXX" + m.group(0)[-4:], text)
    text = ACCOUNT.sub(lambda m: "X" * (len(m.group(0)) - 4) + m.group(0)[-4:], text)
    return IFSC.sub("XXXX0XXXXXX", text)


def redact(value: Any) -> Any:
    if isinstance(value, str):
        return mask_text(value)
    if isinstance(value, dict):
        return {k: ("[redacted]" if k in SENSITIVE_KEYS else redact(v)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value
