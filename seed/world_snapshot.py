"""Build scheduling Snapshots from the shared synthetic world (no database)."""

from __future__ import annotations

from datetime import date, timedelta

from scheduling.model import Employee, Outlet, Policy, Requirement, Shift, Snapshot, Template, Window
from seed import world


def build(
    outlet_key: str = "indiranagar",
    week: date = world.NEXT_WEEK,
    *,
    with_bench: bool = False,
    **overrides: object,
) -> Snapshot:
    """with_bench adds the seed's 7 bench staff per outlet (20 employees, as in the database seed)."""
    outlet_id = world.uid("outlet", outlet_key)
    employees = {
        world.uid("employee", e.key): Employee(
            id=world.uid("employee", e.key),
            name=e.name,
            home_outlet_id=outlet_id,
            status="active",
            skill_ids=frozenset(world.SKILL[k] for k in e.skills),
            rate_paise_per_hour=e.rate_rupees * 100,
            regular_weekly_minutes=2880,
            max_weekly_minutes=2880,
            overtime_allowed=False,
            windows=tuple(Window(*w) for w in world.availability_windows(e)),
        )
        for e in staff_for(outlet_key, with_bench)
    }
    requirements = []
    for d in range(7):
        day = week + timedelta(days=d)
        for skill in ("Grill", "Prep", "Server", "Cashier"):
            for m in range(world.OPEN, world.CLOSE, world.INTERVAL):
                mn, pref = world.requirement(skill, day.weekday(), m)
                if pref:
                    requirements.append(
                        Requirement(
                            outlet_id,
                            world.SKILL[skill],
                            world.at(day, m),
                            world.at(day, m + world.INTERVAL),
                            mn,
                            pref,
                        )
                    )
    templates = tuple(
        Template(
            world.uid("template", f"{outlet_key}:{t.key}"),
            t.start,
            t.end - t.start,
            30 if t.break_start is not None else 0,
            t.break_start - t.start if t.break_start is not None else None,
        )
        for t in world.TEMPLATES.values()
    )
    outlet = Outlet(
        outlet_id, outlet_key.title(), world.TZ, {d: ((world.OPEN, world.CLOSE),) for d in range(7)}
    )
    snap = Snapshot(
        outlet_id,
        week,
        Policy(),
        {outlet_id: outlet},
        employees,
        {v: k for k, v in world.SKILL.items()},
        tuple(requirements),
        templates=templates,
    )
    return Snapshot(**{**snap.__dict__, **overrides})


def staff_for(outlet_key: str, with_bench: bool) -> list[world.Emp]:
    if not with_bench:
        return list(world.STAFF[outlet_key])
    from seed.v2 import bench  # local import: seed.v2 pulls in the database layer

    return [*world.STAFF[outlet_key], *bench(outlet_key)]


def greedy_roster(outlet_key: str = "indiranagar", week: date = world.NEXT_WEEK) -> list[Shift]:
    """The fixture-world greedy roster: the documented feasible baseline."""
    outlet_id = world.uid("outlet", outlet_key)
    out = []
    for sh in world.build_roster(week, with_preferred_extras=True, staff=world.STAFF[outlet_key]):
        _, logical = world.shift_identity(outlet_key, "baseline", sh.key)
        t = sh.template
        out.append(
            Shift(
                logical,
                outlet_id,
                world.uid("employee", sh.employee) if sh.employee else None,
                world.SKILL[sh.skill],
                world.at(sh.day, t.start),
                world.at(sh.day, t.end),
                30 if t.break_start is not None else 0,
                world.at(sh.day, t.break_start) if t.break_start is not None else None,
            )
        )
    return out
