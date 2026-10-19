"""Lossless JSON form of a Snapshot, stored as optimization_runs.input_snapshot.

The worker solves from this document alone (no database reads while solving), so a retry sees
identical input and results are reproducible from (input_hash, config). Bump SCHEMA_VERSION when the
shape changes; the worker refuses versions it does not know.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any
from uuid import UUID

from scheduling.model import Absence, Employee, Outlet, Policy, Requirement, Shift, Snapshot, Template, Window

SCHEMA_VERSION = 1


def _shift(sh: Shift) -> dict[str, Any]:
    return {
        "logical_id": str(sh.logical_id),
        "outlet_id": str(sh.outlet_id),
        "employee_id": str(sh.employee_id) if sh.employee_id else None,
        "skill_id": str(sh.skill_id),
        "start_at": sh.start_at.isoformat(),
        "end_at": sh.end_at.isoformat(),
        "break_minutes": sh.break_minutes,
        "break_start_at": sh.break_start_at.isoformat() if sh.break_start_at else None,
        "locked": sh.locked,
    }


def _shift_back(d: dict[str, Any]) -> Shift:
    return Shift(
        UUID(d["logical_id"]),
        UUID(d["outlet_id"]),
        UUID(d["employee_id"]) if d["employee_id"] else None,
        UUID(d["skill_id"]),
        datetime.fromisoformat(d["start_at"]),
        datetime.fromisoformat(d["end_at"]),
        d["break_minutes"],
        datetime.fromisoformat(d["break_start_at"]) if d["break_start_at"] else None,
        d["locked"],
    )


def dump(snap: Snapshot) -> dict[str, Any]:
    return {
        "snapshot_schema_version": SCHEMA_VERSION,
        "outlet_id": str(snap.outlet_id),
        "week_start": snap.week_start.isoformat(),
        "policy": {
            "min_rest_minutes": snap.policy.min_rest_minutes,
            "grid_minutes": snap.policy.grid_minutes,
            "ot_multiplier_bp": snap.policy.ot_multiplier_bp,
        },
        "outlets": [
            {
                "id": str(o.id),
                "name": o.name,
                "timezone": o.timezone,
                "operating_hours": {
                    str(d): [list(span) for span in spans] for d, spans in sorted(o.operating_hours.items())
                },
            }
            for o in sorted(snap.outlets.values(), key=lambda o: str(o.id))
        ],
        "employees": [
            {
                "id": str(e.id),
                "name": e.name,
                "home_outlet_id": str(e.home_outlet_id),
                "status": e.status,
                "skill_ids": sorted(str(k) for k in e.skill_ids),
                "rate_paise_per_hour": e.rate_paise_per_hour,
                "regular_weekly_minutes": e.regular_weekly_minutes,
                "max_weekly_minutes": e.max_weekly_minutes,
                "overtime_allowed": e.overtime_allowed,
                "windows": [[w.weekday, w.start_minute, w.end_minute, w.kind] for w in e.windows],
            }
            for e in sorted(snap.employees.values(), key=lambda e: str(e.id))
        ],
        "skill_names": {str(k): v for k, v in sorted(snap.skill_names.items(), key=lambda kv: str(kv[0]))},
        "requirements": [
            [
                str(r.outlet_id),
                str(r.skill_id),
                r.interval_start.isoformat(),
                r.interval_end.isoformat(),
                r.minimum,
                r.preferred,
            ]
            for r in snap.requirements
        ],
        "absences": [
            [str(a.employee_id), a.start_at.isoformat(), a.end_at.isoformat(), a.status]
            for a in snap.absences
        ],
        "travel_minutes": [[str(a), str(b), m] for (a, b), m in sorted(snap.travel_minutes.items(), key=str)],
        "commitments": [_shift(sh) for sh in snap.commitments],
        "base_locked": [_shift(sh) for sh in snap.base_locked.values()],
        "templates": [
            {
                "id": str(t.id),
                "start_minute": t.start_minute,
                "duration_minutes": t.duration_minutes,
                "break_minutes": t.break_minutes,
                "break_offset_minutes": t.break_offset_minutes,
                "skill_id": str(t.skill_id) if t.skill_id else None,
            }
            for t in snap.templates
        ],
    }


def load(doc: dict[str, Any]) -> Snapshot:
    if doc.get("snapshot_schema_version") != SCHEMA_VERSION:
        raise ValueError(f"unsupported snapshot_schema_version {doc.get('snapshot_schema_version')!r}")
    outlets = {
        UUID(o["id"]): Outlet(
            UUID(o["id"]),
            o["name"],
            o["timezone"],
            {int(d): tuple((a, b) for a, b in spans) for d, spans in o["operating_hours"].items()},
        )
        for o in doc["outlets"]
    }
    employees = {
        UUID(e["id"]): Employee(
            UUID(e["id"]),
            e["name"],
            UUID(e["home_outlet_id"]),
            e["status"],
            frozenset(UUID(k) for k in e["skill_ids"]),
            e["rate_paise_per_hour"],
            e["regular_weekly_minutes"],
            e["max_weekly_minutes"],
            e["overtime_allowed"],
            tuple(Window(*w) for w in e["windows"]),
        )
        for e in doc["employees"]
    }
    base_locked = [_shift_back(d) for d in doc["base_locked"]]
    return Snapshot(
        outlet_id=UUID(doc["outlet_id"]),
        week_start=date.fromisoformat(doc["week_start"]),
        policy=Policy(**doc["policy"]),
        outlets=outlets,
        employees=employees,
        skill_names={UUID(k): v for k, v in doc["skill_names"].items()},
        requirements=tuple(
            Requirement(UUID(o), UUID(k), datetime.fromisoformat(a), datetime.fromisoformat(b), mn, pf)
            for o, k, a, b, mn, pf in doc["requirements"]
        ),
        absences=tuple(
            Absence(UUID(e), datetime.fromisoformat(a), datetime.fromisoformat(b), st)
            for e, a, b, st in doc["absences"]
        ),
        travel_minutes={(UUID(a), UUID(b)): m for a, b, m in doc["travel_minutes"]},
        commitments=tuple(_shift_back(d) for d in doc["commitments"]),
        base_locked={sh.logical_id: sh for sh in base_locked},
        templates=tuple(
            Template(
                UUID(t["id"]),
                t["start_minute"],
                t["duration_minutes"],
                t["break_minutes"],
                t["break_offset_minutes"],
                UUID(t["skill_id"]) if t["skill_id"] else None,
            )
            for t in doc["templates"]
        ),
    )


def digest(doc: dict[str, Any]) -> str:
    return (
        "sha256:"
        + hashlib.sha256(json.dumps(doc, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    )


def shift_doc(sh: Shift) -> dict[str, Any]:
    return _shift(sh)


def shift_from_doc(d: dict[str, Any]) -> Shift:
    return _shift_back(d)


def absence_doc(a: Absence) -> dict[str, Any]:
    return {
        "employee_id": str(a.employee_id),
        "start_at": a.start_at.isoformat(),
        "end_at": a.end_at.isoformat(),
        "status": a.status,
    }


def absence_from_doc(d: dict[str, Any]) -> Absence:
    return Absence(
        UUID(d["employee_id"]),
        datetime.fromisoformat(d["start_at"]),
        datetime.fromisoformat(d["end_at"]),
        d["status"],
    )
