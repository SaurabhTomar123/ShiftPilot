"""Money helpers. All amounts are INR as Decimal with 2 places; never floats."""

from decimal import ROUND_HALF_UP, Decimal

PAISA = Decimal("0.01")


def inr(value: Decimal | int | str) -> Decimal:
    return Decimal(value).quantize(PAISA, rounding=ROUND_HALF_UP)


def fmt_inr(value: Decimal) -> str:
    """Format with Indian digit grouping: 123456.5 -> '₹1,23,456.50'. Drops '.00'."""
    sign = "-" if value < 0 else ""
    value = abs(inr(value))
    whole, frac = f"{value:.2f}".split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        groups: list[str] = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        whole = ",".join(groups) + "," + tail
    return f"{sign}₹{whole}" if frac == "00" else f"{sign}₹{whole}.{frac}"
