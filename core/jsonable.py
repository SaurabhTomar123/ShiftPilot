from datetime import date, datetime, time
from decimal import Decimal
from typing import Any
from uuid import UUID


def jsonable(value: Any) -> Any:
    """Convert DB/domain values into JSON-safe primitives (Decimals as strings, never floats)."""
    if isinstance(value, Decimal | UUID):
        return str(value)
    if isinstance(value, datetime | date | time):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [jsonable(v) for v in value]
    return value
