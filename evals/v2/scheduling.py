"""Scheduling evaluation scenarios (architecture v3 section 42): normal, impossible, overtime,
multi_outlet, locks, repair and rules. Offline: every scenario is built from the synthetic world.

Each scenario returns (passed, detail). A scenario checks properties v3 promises, never a specific
roster: every candidate is valid; impossible weeks are diagnosed, not answered with an invalid roster;
locks survive; repairs remove the absent person and stay local; rules bind.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import date, timedelta

from scheduling import metrics, repair, rules, solver, validator
from scheduling.model import Absence, Requirement, Snapshot
from seed import world
from seed.world_snapshot import build, greedy_roster

TIME = 4.0


@dataclass(frozen=True)
class Scenario:
    suite: str
    name: str
    run: Callable[[], tuple[bool, str]]


def _valid(snap: Snapshot, out: solver.Outcome) -> tuple[bool, str]:
    if not out.candidates:
        return False, f"no candidate ({out.status})"
    for c in out.candidates:
        check = validator.validate(snap, c.roster)
        if not check.valid:
            return (
                False,
                f"{c.strategy}: {sorted({v.code for v in check.violations if v.severity == 'hard'})}",
            )
    return True, f"{len(out.candidates)} valid candidates, {out.status}"


def normal(outlet: str, week: date, strategy: str) -> Scenario:
    def run() -> tuple[bool, str]:
        snap = build(outlet, week)
        out = solver.generate(snap, strategy, time_limit=TIME, max_candidates=1)
        ok, detail = _valid(snap, out)
        if ok and metrics.compute(snap, out.candidates[0].roster).minimum_deficit_minutes:
            return False, "minimum staffing not kept"
        return ok, detail

    return Scenario("normal", f"{outlet}-{week}-{strategy}", run)


def impossible(skill: str, extra: int, weekday: int) -> Scenario:
    def run() -> tuple[bool, str]:
        snap = build()
        day = world.NEXT_WEEK + timedelta(days=weekday)
        people = sum(1 for e in snap.employees.values() if world.SKILL[skill] in e.skill_ids)
        need = people + extra
        spike = tuple(
            Requirement(
                snap.outlet_id, world.SKILL[skill], world.at(day, m), world.at(day, m + 30), need, need
            )
            for m in range(1080, 1260, 30)
        )
        keep = tuple(
            r
            for r in snap.requirements
            if (r.skill_id, r.interval_start) not in {(x.skill_id, x.interval_start) for x in spike}
        )
        out = solver.generate(replace(snap, requirements=(*keep, *spike)), "balanced", time_limit=TIME)
        kinds = [r.kind for r in out.relaxations]
        ok = (
            out.status == "INFEASIBLE"
            and not out.candidates
            and bool(out.shortages)
            and "reduced_minimum" in kinds
        )
        return ok, f"{out.status}, options {kinds}"

    return Scenario("impossible", f"{skill}+{extra}-day{weekday}", run)


def overtime(regular_hours: int) -> Scenario:
    def run() -> tuple[bool, str]:
        snap = build()
        capped = {
            e.id: replace(
                e, regular_weekly_minutes=regular_hours * 60, max_weekly_minutes=2880, overtime_allowed=False
            )
            for e in snap.employees.values()
        }
        tight = replace(snap, employees=capped)
        out = solver.generate(tight, "balanced", time_limit=TIME, max_candidates=1)
        if out.candidates:
            return _valid(tight, out)  # the cap still allowed a roster: it must respect it
        kinds = [r.kind for r in out.relaxations]
        return out.status == "INFEASIBLE" and "overtime" in kinds, f"{out.status}, options {kinds}"

    return Scenario("overtime", f"regular-{regular_hours}h", run)


def locks(count: int) -> Scenario:
    def run() -> tuple[bool, str]:
        snap = build()
        base = greedy_roster()
        locked = [replace(s, locked=True) for s in base if s.employee_id][::7][:count]
        out = solver.generate(
            replace(snap, base_locked={s.logical_id: s for s in locked}),
            "balanced",
            time_limit=TIME,
            max_candidates=1,
        )
        if not out.candidates:
            return False, out.status
        kept = {(s.logical_id, s.employee_id, s.start_at) for s in out.candidates[0].roster}
        ok = all((s.logical_id, s.employee_id, s.start_at) in kept for s in locked)
        return ok, f"{len(locked)} locks kept" if ok else "a locked shift changed"

    return Scenario("locks", f"{count}-locked", run)


def repaired(outlet: str, weekday: int, nth: int) -> Scenario:
    def run() -> tuple[bool, str]:
        snap = build(outlet, world.NEXT_WEEK)
        base = greedy_roster(outlet)
        tz = snap.outlet.tz
        day = [
            s
            for s in base
            if s.employee_id and not s.locked and s.start_at.astimezone(tz).weekday() == weekday
        ]
        if len(day) <= nth:
            return True, "no shift to repair that day"
        victim = day[nth]
        absence = Absence(victim.employee_id, victim.start_at, victim.end_at, "confirmed")  # type: ignore[arg-type]
        out = repair.repair(snap, base, absence, time_limit=TIME)
        if not out.plans:
            return False, f"no plan ({out.status})"
        plan = out.plans[0]
        fixed = next(s for s in plan.roster if s.logical_id == victim.logical_id)
        stage = next(r["stage"] for r in out.widening if r["result"] == "selected")
        local = plan.disruption["changed_shifts"] + plan.disruption["added_shifts"] <= 6
        ok = fixed.employee_id != victim.employee_id and local
        return ok, f"stage {stage}, disruption {plan.disruption}"

    return Scenario("repair", f"{outlet}-day{weekday}-#{nth}", run)


def ruled(rule_type: str, value: int) -> Scenario:
    def run() -> tuple[bool, str]:
        snap = build()
        tz = snap.outlet.tz
        free = solver.solve(snap, "balanced", time_limit=TIME)[1]
        if free is None:
            return False, "baseline infeasible"
        if rule_type == "max_shift_end_time":
            rule = rules.Rule(
                world.uid("rule", f"end{value}"),
                rule_type,
                "organization",
                {},
                {"latest_end_minute": value, "weekdays": list(range(7))},
            )
            who = [
                e
                for e, _ in Counter(
                    s.employee_id for s in free.roster if rules.end_allowed([rule], s.start_at, s.end_at, tz)
                ).most_common(2)
            ]
        else:
            rule = rules.Rule(
                world.uid("rule", f"days{value}"), rule_type, "organization", {}, {"days": value}
            )
            worked = Counter(
                e for e, _ in {(s.employee_id, s.start_at.astimezone(tz).date()) for s in free.roster}
            )
            who = [e for e, _ in worked.most_common(2)]
        bound = replace(snap, rules={e: (rule,) for e in who if e})
        out = solver.generate(bound, "balanced", time_limit=TIME, max_candidates=1)
        return _valid(bound, out)

    return Scenario("rules_enforced", f"{rule_type}-{value}", run)


def multi_outlet() -> list[Scenario]:
    def borrow(outlet: str, lender: str) -> Scenario:
        def run() -> tuple[bool, str]:
            home, other = build(outlet), build(lender)
            cooks = sum(1 for e in home.employees.values() if world.SKILL["Grill"] in e.skill_ids)
            day = world.NEXT_WEEK + timedelta(days=4)
            spike = tuple(
                Requirement(
                    home.outlet_id,
                    world.SKILL["Grill"],
                    world.at(day, m),
                    world.at(day, m + 30),
                    cooks + 1,
                    cooks + 1,
                )
                for m in range(1140, 1320, 30)
            )
            keep = tuple(
                r
                for r in home.requirements
                if (r.skill_id, r.interval_start) not in {(x.skill_id, x.interval_start) for x in spike}
            )
            wide = replace(
                home,
                requirements=(*keep, *spike),
                employees={**home.employees, **other.employees},
                outlets={**home.outlets, **other.outlets},
            )
            out = solver.generate(wide, "balanced", time_limit=TIME)
            kinds = [r.kind for r in out.relaxations]
            own_only = all(s.employee_id in home.employees for c in out.candidates for s in c.roster)
            return out.status == "INFEASIBLE" and "cross_outlet" in kinds and own_only, f"options {kinds}"

        return Scenario("multi_outlet", f"{outlet}<-{lender}", run)

    return [borrow("indiranagar", "koramangala"), borrow("koramangala", "hsr"), borrow("hsr", "indiranagar")]


def scenarios() -> list[Scenario]:
    out: list[Scenario] = []
    for outlet, _ in world.OUTLETS:
        for week in (world.WEEK, world.NEXT_WEEK):
            for strategy in solver.ALTERNATIVES:
                out.append(normal(outlet, week, strategy))
    out += [
        impossible(skill, extra, wd)
        for skill, extra, wd in (
            ("Grill", 1, 4),
            ("Grill", 3, 5),
            ("Server", 2, 4),
            ("Cashier", 2, 6),
            ("Prep", 3, 1),
        )
    ]
    out += [overtime(h) for h in (8, 10, 12, 16, 20)]
    out += [locks(n) for n in (1, 3, 5, 8, 12)]
    out += [
        repaired(outlet, wd, nth)
        for outlet in ("indiranagar", "koramangala")
        for wd, nth in ((0, 0), (2, 1), (4, 0), (5, 2), (6, 1))
    ]
    out += [ruled("max_shift_end_time", m) for m in (1200, 1260, 1290)] + [
        ruled("max_days_per_week", d) for d in (3, 4)
    ]
    out += multi_outlet()
    return out
