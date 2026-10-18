"""Deterministic synthetic data: 1 org, 3 outlets, 60 staff, 8 weekly pay periods, planted
anomalies, and the ground-truth answers the eval suite checks against.

Pure: no database. `seed.load` writes the result to Postgres.

    python -m seed.generate --seed 42      # writes seed/ground_truth.json only
"""

from __future__ import annotations

import argparse
import json
import random
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from core.clock import IST  # noqa: E402
from core.money import fmt_inr, inr
from core.payroll import (
    DeductionLine,
    OtRule,
    Payslip,
    WorkDay,
    compute_payslip,
    diff_payslips,
    worked_hours,
)

START = date(2026, 8, 17)  # Monday
WEEKS = 8
NS = uuid.UUID("6f1f7a52-2b1e-4c55-9d1a-5e8f00c0ffee")
GROUND_TRUTH_PATH = Path(__file__).with_name("ground_truth.json")

OUTLETS = [
    # slug, name, area, tip method, roles
    ("cafe_indiranagar", "Brew Lane Café", "Indiranagar", "hours_weighted",
     ["barista", "barista", "server", "server", "cook", "cashier", "cleaner"]),
    ("qsr_koramangala", "Tandoor Express", "Koramangala", "equal",
     ["cook", "cook", "server", "cashier", "cleaner"]),
    ("kitchen_hsr", "Cloud Kitchen HSR", "HSR Layout", None,
     ["cook", "cook", "cook", "packer", "cleaner"]),
]
RATE_RANGE = {"cook": (140, 170), "barista": (120, 140), "server": (110, 130),
              "cashier": (115, 130), "cleaner": (95, 110), "packer": (100, 115)}
SHIFT_TEMPLATES = {"opening": (time(7), time(15)), "mid": (time(11), time(19)),
                   "closing": (time(15), time(23))}
FIRST = ["Aarav", "Vihaan", "Ananya", "Diya", "Arjun", "Priya", "Karthik", "Sneha", "Rahul",
         "Lakshmi", "Manoj", "Divya", "Suresh", "Kavya", "Nikhil", "Pooja", "Ramesh", "Meghana",
         "Sanjay", "Asha", "Vikram", "Deepa", "Kiran", "Swathi", "Harish", "Nandini", "Gopal",
         "Rekha", "Ajay", "Bhavana", "Naveen", "Shruti", "Mohan", "Anjali", "Prakash", "Keerthi",
         "Venkat", "Sahana", "Imran", "Fatima", "Joseph", "Mary", "Sunil", "Geetha", "Ashok",
         "Radha", "Tarun", "Usha", "Yash", "Zoya", "Irfan", "Neha", "Rohit", "Sowmya", "Ganesh",
         "Pallavi", "Abdul", "Chitra"]
LAST = ["Sharma", "Reddy", "Nair", "Gowda", "Iyer", "Shetty", "Rao", "Khan", "Das", "Pillai",
        "Hegde", "Patil", "Menon", "Singh", "Joshi", "Naidu", "Bhat", "Kulkarni", "Thomas", "Ali"]
CHECKLIST = {
    "opening": ["Unlock and disarm alarm", "Check fridge temperatures", "Switch on equipment",
                "Count opening cash float", "Sanitise counters", "Check stock deliveries",
                "Brief the team", "Unlock customer doors"],
    "closing": ["Clean grills and fryers", "Record fridge temperatures", "Cash-up and safe drop",
                "Empty bins", "Mop floors", "Switch off equipment", "Lock storerooms",
                "Arm alarm and lock up"],
}


def uid(*parts: object) -> str:
    return str(uuid.uuid5(NS, "/".join(str(p) for p in parts)))


def week_start(i: int) -> date:
    return START + timedelta(weeks=i)


@dataclass
class Dataset:
    tables: dict[str, list[dict[str, Any]]] = field(default_factory=lambda: defaultdict(list))
    ground_truth: dict[str, Any] = field(default_factory=dict)


def generate(seed: int = 42) -> Dataset:
    rng = random.Random(seed)
    ds = Dataset()
    t = ds.tables

    org_id = uid("org")
    rule_id = uid("ot_rule")
    rule = OtRule()
    t["organizations"].append({"id": org_id, "name": "Chai & Co Hospitality", "plan": "demo"})
    t["ot_rules"].append({"id": rule_id, "org_id": org_id, "daily_threshold_hrs": rule.daily_threshold_hrs,
                          "weekly_threshold_hrs": rule.weekly_threshold_hrs, "multiplier": rule.multiplier})
    t["users"].append({"id": uid("user", "owner"), "org_id": org_id, "outlet_id": None,
                       "employee_id": None, "name": "Meera Iyer", "phone": "+919800000001",
                       "role": "owner", "is_active": True})

    names = [f"{first} {last}" for first in FIRST for last in LAST]
    rng.shuffle(names)
    names = [n for n in names if not n.startswith("Ravi")]
    employees: list[dict[str, Any]] = []
    rate_of: dict[str, list[tuple[date, Decimal]]] = {}

    for o_idx, (slug, name, area, _tip, roles) in enumerate(OUTLETS):
        outlet_id = uid("outlet", slug)
        t["outlets"].append({"id": outlet_id, "org_id": org_id, "name": name, "slug": slug,
                             "city": f"{area}, Bengaluru", "timezone": "Asia/Kolkata",
                             "ot_rule_id": rule_id})
        t["users"].append({"id": uid("user", "manager", slug), "org_id": org_id,
                           "outlet_id": outlet_id, "employee_id": None,
                           "name": ["Arun Menon", "Farah Sheikh", "Deepak Rao"][o_idx],
                           "phone": f"+91980000000{o_idx + 2}", "role": "manager", "is_active": True})
        for e_idx in range(20):
            if slug == "cafe_indiranagar" and e_idx == 0:
                emp_name, aliases, role = "Ravi Kumar", ["Ravi"], "server"
            elif slug == "cafe_indiranagar" and e_idx == 1:
                emp_name, aliases, role = "Ravi K", ["Ravi", "Ravi Krishnan"], "cook"
            else:
                emp_name, aliases, role = names.pop(), [], roles[e_idx % len(roles)]
            emp_id = uid("employee", slug, e_idx)
            lo, hi = RATE_RANGE[role]
            rate = Decimal(rng.randint(lo, hi))
            phone = f"+9197{o_idx}{e_idx:02d}{rng.randint(10000, 99999)}"
            emp = {"id": emp_id, "org_id": org_id, "outlet_id": outlet_id, "name": emp_name,
                   "aliases": aliases, "job_role": role, "pay_type": "hourly", "hourly_rate": rate,
                   "monthly_base": None, "phone": phone,
                   "joined_on": START - timedelta(days=rng.randint(60, 900)), "status": "active",
                   # generator-only helpers (stripped before insert)
                   "_slug": slug, "_template": ["opening", "mid", "closing"][e_idx % 3],
                   "_days": 6 if (e_idx % 4 or emp_name == "Ravi Kumar") else 5,
                   "_off": rng.randint(0, 6)}
            employees.append(emp)
            rate_of[emp_id] = [(emp["joined_on"], rate)]
            t["users"].append({"id": uid("user", "staff", emp_id), "org_id": org_id,
                               "outlet_id": outlet_id, "employee_id": emp_id, "name": emp_name,
                               "phone": phone, "role": "staff", "is_active": True})

    by_name = {e["name"]: e for e in employees}
    ravi = by_name["Ravi Kumar"]

    # Planted anomaly: one mid-period rate change (Wednesday of week 5).
    changed = employees[5]
    change_day = week_start(4) + timedelta(days=2)
    old_rate = changed["hourly_rate"]
    new_rate = old_rate + 15
    rate_of[changed["id"]].append((change_day, new_rate))
    changed["hourly_rate"] = new_rate
    for emp in employees:
        for eff, rate in rate_of[emp["id"]]:
            t["rate_history"].append({"id": uid("rate", emp["id"], eff), "org_id": org_id,
                                      "employee_id": emp["id"], "effective_from": eff,
                                      "hourly_rate": rate})

    def rate_on(emp_id: str, day: date) -> Decimal:
        return [r for eff, r in rate_of[emp_id] if eff <= day][-1]

    # Pay periods
    period_id: dict[tuple[str, int], str] = {}
    for slug, *_ in OUTLETS:
        for w in range(WEEKS):
            pid = uid("period", slug, w)
            period_id[(slug, w)] = pid
            t["pay_periods"].append({"id": pid, "org_id": org_id, "outlet_id": uid("outlet", slug),
                                     "start_date": week_start(w),
                                     "end_date": week_start(w) + timedelta(days=6),
                                     "status": "paid" if w < 6 else ("locked" if w == 6 else "open")})

    # Shifts + attendance
    attendance: list[dict[str, Any]] = []
    shift_end: dict[str, datetime] = {}
    for emp in employees:
        start_t, end_t = SHIFT_TEMPLATES[emp["_template"]]
        for w in range(WEEKS):
            days_off = {emp["_off"]} if emp["_days"] == 6 else {emp["_off"], (emp["_off"] + 3) % 7}
            if emp is ravi and w == WEEKS - 1:
                days_off = {0, 2, 6}  # Ravi works 4 shifts in the final week
            for d in range(7):
                if d in days_off:
                    continue
                day = week_start(w) + timedelta(days=d)
                sid = uid("shift", emp["id"], day)
                t["shifts"].append({"id": sid, "org_id": org_id, "outlet_id": emp["outlet_id"],
                                    "employee_id": emp["id"], "day": day, "start_time": start_t,
                                    "end_time": end_t, "job_role": emp["job_role"],
                                    "label": emp["_template"], "status": "scheduled", "version": 1})
                s_start = datetime.combine(day, start_t, IST)
                s_end = datetime.combine(day, end_t, IST)
                extra = rng.randint(60, 150) if rng.random() < 0.05 else 0
                att = {"id": uid("att", sid), "org_id": org_id, "shift_id": sid,
                       "employee_id": emp["id"],
                       "clock_in": s_start + timedelta(minutes=rng.randint(-10, 12)),
                       "clock_out": s_end + timedelta(minutes=rng.randint(-5, 25) + extra),
                       "source": "app", "note": None}
                attendance.append(att)
                shift_end[att["id"]] = s_end

    # Planted anomalies on attendance (late weeks so they show up in "recent" questions).
    recent = sorted((a for a in attendance if a["clock_in"].date() >= week_start(5)
                     and a["employee_id"] != ravi["id"]), key=lambda a: a["id"])
    picks = rng.sample(recent, 10)
    missing, spikes = picks[:6], picks[6:]
    for a in missing:
        a["clock_out"] = None
    for a in spikes:
        a["clock_out"] = a["clock_in"] + timedelta(minutes=rng.randint(13 * 60 + 5, 14 * 60 + 30))
    t["attendance"] = attendance

    hours_of: dict[str, Decimal] = {}
    for a in attendance:
        hours_of[a["id"]], _ = worked_hours(a["clock_in"], a["clock_out"], shift_end[a["id"]])

    # Tips
    emp_by_id = {e["id"]: e for e in employees}
    worked_on: dict[tuple[str, date], list[dict[str, Any]]] = defaultdict(list)
    for a in attendance:
        emp = emp_by_id[a["employee_id"]]
        worked_on[(emp["_slug"], a["clock_in"].date())].append(a)
    tip_alloc: dict[tuple[str, date], Decimal] = defaultdict(Decimal)
    tip_rows: list[dict[str, Any]] = []
    for slug, _name, _area, method, _roles in OUTLETS:
        if method is None:
            continue
        lo, hi = (150, 350) if slug == "cafe_indiranagar" else (80, 200)
        for i in range(WEEKS * 7):
            day = START + timedelta(days=i)
            total = inr(rng.randint(lo, hi) * 10)
            tip_id = uid("tip", slug, day)
            tip_rows.append({"id": tip_id, "org_id": org_id, "outlet_id": uid("outlet", slug),
                             "day": day, "total_amount": total, "method": method})
            workers = sorted(worked_on[(slug, day)], key=lambda a: a["employee_id"])
            if not workers:
                continue
            weights = [hours_of[a["id"]] if method == "hours_weighted" else Decimal(1)
                       for a in workers]
            weight_sum = sum(weights, Decimal(0))
            shares = [inr(total * w / weight_sum) for w in weights]
            shares[-1] += total - sum(shares, Decimal(0))  # rounding remainder to the last share
            for a, share in zip(workers, shares, strict=True):
                t["tip_allocations"].append({"id": uid("tipalloc", tip_id, a["employee_id"]),
                                             "org_id": org_id, "tip_id": tip_id,
                                             "employee_id": a["employee_id"], "amount": share})
    t["tips"] = tip_rows
    # Planted anomaly: 2 days where allocations don't add up to the tips collected.
    mismatch_tips = rng.sample([r for r in tip_rows if r["day"] >= week_start(5)], 2)
    for tip in mismatch_tips:
        alloc = next(a for a in t["tip_allocations"] if a["tip_id"] == tip["id"])
        alloc["amount"] -= inr(rng.randint(15, 40) * 10)
    tip_day_of = {r["id"]: r["day"] for r in tip_rows}
    for alloc in t["tip_allocations"]:
        tip_alloc[(alloc["employee_id"], tip_day_of[alloc["tip_id"]])] += alloc["amount"]

    # Deductions
    deductions: list[dict[str, Any]] = []

    def add_ded(emp: dict[str, Any], w: int, ded_type: str, amount: Decimal, note: str,
                n: int = 0) -> dict[str, Any]:
        row = {"id": uid("ded", emp["id"], w, ded_type, n), "org_id": org_id,
               "employee_id": emp["id"], "pay_period_id": period_id[(emp["_slug"], w)],
               "type": ded_type, "amount": inr(amount), "note": note, "created_by": None}
        deductions.append(row)
        return row

    meal_takers = [e for e in employees if rng.random() < 0.3]
    for emp in meal_takers:
        amount = Decimal(rng.choice([150, 200, 250, 300]))
        for w in range(WEEKS):
            add_ded(emp, w, "meal", amount, "Staff meals")
    for emp in rng.sample(employees, 5):
        add_ded(emp, rng.randint(0, WEEKS - 1), "advance", Decimal(rng.randint(10, 30) * 100),
                "Salary advance recovery")
    add_ded(ravi, WEEKS - 1, "uniform", Decimal(240), "Replacement apron and cap")
    for emp in rng.sample([e for e in employees if e is not ravi], 3):
        add_ded(emp, rng.randint(0, WEEKS - 1), "uniform", Decimal(240), "Uniform set")
    # Planted anomaly: 3 duplicated meal deductions.
    dup_sources = rng.sample([d for d in deductions if d["type"] == "meal"
                              and d["pay_period_id"] in {period_id[(s, w)] for s, *_ in OUTLETS
                                                         for w in (5, 6, 7)}], 3)
    for d in dup_sources:
        deductions.append({**d, "id": uid("ded-dup", d["id"])})
    t["deductions"] = deductions

    # Payslips via the same deterministic engine the tools use.
    att_by_emp_week: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for a in attendance:
        w = (a["clock_in"].date() - START).days // 7
        att_by_emp_week[(a["employee_id"], w)].append(a)
    ded_by_emp_period: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for d in deductions:
        ded_by_emp_period[(d["employee_id"], d["pay_period_id"])].append(d)

    slips: dict[tuple[str, int], Payslip] = {}
    for emp in employees:
        for w in range(WEEKS):
            rows = att_by_emp_week[(emp["id"], w)]
            work_days = [WorkDay(a["clock_in"].date(), hours_of[a["id"]],
                                 rate_on(emp["id"], a["clock_in"].date())) for a in rows]
            tips = [tip_alloc[(emp["id"], a["clock_in"].date())] for a in rows
                    if (emp["id"], a["clock_in"].date()) in tip_alloc]
            pid = period_id[(emp["_slug"], w)]
            deds = [DeductionLine(d["type"], d["amount"], d["note"])
                    for d in ded_by_emp_period[(emp["id"], pid)]]
            slip = compute_payslip(work_days, tips, deds, rule)
            slips[(emp["id"], w)] = slip
            t["payslips"].append({"id": uid("slip", emp["id"], w), "org_id": org_id,
                                  "employee_id": emp["id"], "pay_period_id": pid,
                                  "shifts_worked": slip.shifts_worked,
                                  "regular_hours": slip.regular_hours, "ot_hours": slip.ot_hours,
                                  "base_pay": slip.base_pay, "ot_pay": slip.ot_pay,
                                  "tips_total": slip.tips_total,
                                  "deductions_total": slip.deductions_total,
                                  "net_pay": slip.net_pay, "detail": slip.to_json()})

    # Checklists
    staff_at: dict[str, list[str]] = defaultdict(list)
    for e in employees:
        staff_at[e["_slug"]].append(e["id"])
    last_day = START + timedelta(days=WEEKS * 7 - 1)
    missed_days = set(rng.sample(range(WEEKS * 7 - 1), 3))
    for slug, *_ in OUTLETS:
        for i in range(WEEKS * 7):
            day = START + timedelta(days=i)
            for kind, items in CHECKLIST.items():
                cid = uid("checklist", slug, day, kind)
                t["checklists"].append({"id": cid, "org_id": org_id, "outlet_id": uid("outlet", slug),
                                        "day": day, "type": kind})
                base_hour = 7 if kind == "opening" else 22
                for pos, title in enumerate(items):
                    undone = (day == last_day and kind == "closing" and pos >= 6) or (
                        i in missed_days and kind == "closing" and pos == 2 and slug == "cafe_indiranagar")
                    t["checklist_items"].append({
                        "id": uid("item", cid, pos), "org_id": org_id, "checklist_id": cid,
                        "position": pos, "title": title, "required": True,
                        "done_by": None if undone else rng.choice(staff_at[slug]),
                        "done_at": None if undone else datetime.combine(day, time(base_hour, 5 * pos), IST),
                        "note": None})

    # Strip generator-only helper keys.
    for emp in employees:
        for k in [k for k in emp if k.startswith("_")]:
            emp.pop(k)
    t["employees"] = employees

    # ---------------- ground truth for evals ----------------
    name_of = {e["id"]: e["name"] for e in employees}
    gt = ds.ground_truth
    total, changes = diff_payslips(slips[(ravi["id"], WEEKS - 2)], slips[(ravi["id"], WEEKS - 1)])
    gt["ravi_kumar_last_week_vs_previous"] = {
        "net_delta": fmt_inr(total),
        "previous_net": fmt_inr(slips[(ravi["id"], WEEKS - 2)].net_pay),
        "current_net": fmt_inr(slips[(ravi["id"], WEEKS - 1)].net_pay),
        "changes": [{"component": c.component, "delta": fmt_inr(c.delta), "reason": c.reason}
                    for c in changes],
        "facts": [fmt_inr(abs(total)), "2 fewer shifts", fmt_inr(Decimal(240))],
    }
    for key, offset in (("cafe_closing_last_friday", 4), ("cafe_closing_last_saturday", 5)):
        day = week_start(WEEKS - 1) + timedelta(days=offset)
        gt[key] = {
            "day": day.isoformat(),
            "names": sorted(name_of[s["employee_id"]] for s in t["shifts"]
                            if s["day"] == day and s["label"] == "closing"
                            and s["outlet_id"] == uid("outlet", "cafe_indiranagar")),
        }
    gt["missing_clock_outs"] = sorted(
        [{"employee": name_of[a["employee_id"]], "day": a["clock_in"].date().isoformat()}
         for a in missing], key=lambda r: (r["day"], r["employee"]))
    gt["ot_spikes"] = sorted(
        [{"employee": name_of[a["employee_id"]], "day": a["clock_in"].date().isoformat(),
          "hours": str(hours_of[a["id"]])} for a in spikes], key=lambda r: (r["day"], r["employee"]))
    gt["duplicate_deductions"] = sorted(
        [{"employee": name_of[d["employee_id"]], "type": d["type"], "amount": fmt_inr(d["amount"]),
          "period_start": next(p["start_date"].isoformat() for p in t["pay_periods"]
                               if p["id"] == d["pay_period_id"])}
         for d in dup_sources], key=lambda r: r["employee"])
    slug_of = {uid("outlet", s): s for s, *_ in OUTLETS}
    gt["tip_mismatches"] = sorted(
        ({"outlet": slug_of[r["outlet_id"]], "day": r["day"].isoformat()} for r in mismatch_tips),
        key=lambda r: (r["day"], r["outlet"]))
    gt["rate_change"] = {"employee": changed["name"], "effective_from": change_day.isoformat(),
                         "old_rate": fmt_inr(old_rate), "new_rate": fmt_inr(new_rate)}
    gt["outlet_net_payroll_last_week"] = {
        slug: fmt_inr(sum((slips[(e["id"], WEEKS - 1)].net_pay for e in employees
                           if e["outlet_id"] == uid("outlet", slug)), Decimal(0)))
        for slug, *_ in OUTLETS}
    gt["last_week"] = {"start": week_start(WEEKS - 1).isoformat(), "end": last_day.isoformat()}
    gt["users"] = {"owner": "+919800000001", "cafe_manager": "+919800000002",
                   "qsr_manager": "+919800000003", "kitchen_manager": "+919800000004",
                   "ravi_kumar_staff": ravi["phone"]}
    return ds


def write_ground_truth(ds: Dataset, path: Path = GROUND_TRUTH_PATH) -> None:
    path.write_text(json.dumps(ds.ground_truth, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    data = generate(args.seed)
    write_ground_truth(data)
    print({k: len(v) for k, v in data.tables.items()})
