"""A deterministic stand-in for the hosted model, for tests and offline evaluation.

It answers the same prompts with the same JSON a model would, for a fixed set of phrasings, so the
whole pipeline (validation, entity resolution, previews) can be tested without a network or a key. It
is never configured in production: there, language_model names a hosted model.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_TODAY = re.compile(r"TODAY: (\d{4}-\d{2}-\d{2})")


def _clock(text: str) -> int | None:
    m = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", text)
    if not m:
        return None
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) == "pm" and hour < 12:
        hour += 12
    return hour * 60 + minute


def _day(text: str, today: date) -> date | None:
    if "tomorrow" in text:
        return today + timedelta(days=1)
    if "today" in text:
        return today
    for n, name in enumerate(DAYS):
        if name in text:
            ahead = (n - today.weekday()) % 7 or 7
            return today + timedelta(days=ahead)
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    return date.fromisoformat(m.group(1)) if m else None


def _weekdays(text: str) -> list[int]:
    if "weekday" in text:
        return [0, 1, 2, 3, 4]
    named = [n for n, name in enumerate(DAYS) if name in text or name[:3] + "s" in text]
    return named or list(range(7))


class ScriptedModel:
    def complete_json(self, system: str, user: str) -> dict[str, Any]:
        found = _TODAY.search(system)
        today = date.fromisoformat(found.group(1)) if found else date.today()
        text = user.lower().strip()
        return self._rule(text) if "TASK: rule" in system else self._command(text, today)

    def _command(self, text: str, today: date) -> dict[str, Any]:
        m = re.match(
            r"(?:give )?(?P<who>[a-z .]+?)(?: is)? (?:the day )?off (?:on )?(?P<when>.+)", text
        ) or re.match(
            r"give (?P<who>[a-z .]+?) (?P<when>(?:next |this )?(?:monday|tuesday|wednesday|thursday|friday|"
            r"saturday|sunday|today|tomorrow|\d{4}-\d{2}-\d{2})) off",
            text,
        )
        if m:
            return {
                "intent": "give_time_off",
                "employee_query": m["who"].strip().title(),
                "day": str(_day(m["when"], today)),
            }
        m = re.match(r"(?P<who>[a-z .]+?) (?:is|called in) sick(?: (?P<when>.+))?", text)
        if m:
            when = _day(m["when"] or "today", today)
            return {"intent": "report_sick", "employee_query": m["who"].strip().title(), "day": str(when)}
        if text.startswith(("generate", "make", "build")):
            monday = today - timedelta(days=today.weekday())
            week = monday + timedelta(days=7) if "next week" in text else monday
            outlet = re.search(r"(?:for|at) ([a-z ]+?)(?: next week| this week|$)", text)
            return {
                "intent": "generate_week",
                "week_start": str(week),
                "outlet_query": outlet.group(1).title() if outlet else None,
            }
        return {"intent": "unsupported"}

    def _rule(self, text: str) -> dict[str, Any]:
        m = re.search(r"(?:no more than|more than|at most|maximum of|max) (\d) (?:working )?days", text)
        if m:
            scope = re.match(r"(?P<who>[a-z ]+?) (?:can|may|should)", text)
            who = scope["who"] if scope else None
            if who in (None, "staff", "everyone", "employees", "nobody", "no one"):
                return {
                    "supported": True,
                    "rule_type": "max_days_per_week",
                    "scope_level": "organization",
                    "days": int(m.group(1)),
                }
            return {
                "supported": True,
                "rule_type": "max_days_per_week",
                "scope_level": "tag",
                "scope_query": who,
                "days": int(m.group(1)),
            }
        m = re.search(r"(?:later than|after|past|until|by) (\d{1,2}(?::\d{2})?\s*(?:am|pm)?)", text)
        if m and ("work" in text or "finish" in text or "end" in text):
            minute = _clock(m.group(1))
            subject = text.split(" ")[0]
            level = "tag" if subject.endswith("s") else "employee"
            return {
                "supported": True,
                "rule_type": "max_shift_end_time",
                "scope_level": level,
                "scope_query": subject if level == "tag" else text.split(" can")[0].split(" must")[0].title(),
                "latest_end_minute": minute,
                "weekdays": _weekdays(text),
            }
        return {"supported": False, "reason": "That kind of rule is not supported yet."}
