from collections import Counter

from core import anomalies as an
from rag.ingest import chunk_markdown
from seed.generate import generate
from seed.load import POLICY_DIR


def test_generation_is_deterministic() -> None:
    a, b = generate(42), generate(42)
    assert a.ground_truth == b.ground_truth
    assert len(a.tables["shifts"]) == len(b.tables["shifts"])


def test_sizes() -> None:
    t = generate(42).tables
    assert len(t["employees"]) == 60
    assert len(t["outlets"]) == 3
    assert len(t["pay_periods"]) == 24
    assert len(t["payslips"]) == 60 * 8


def test_planted_anomalies() -> None:
    ds = generate(42)
    t, gt = ds.tables, ds.ground_truth
    assert sum(1 for a in t["attendance"] if a["clock_out"] is None) == 6
    assert len(gt["ot_spikes"]) == 4
    dup_keys = Counter((d["employee_id"], d["pay_period_id"], d["type"], d["amount"])
                       for d in t["deductions"])
    assert sum(1 for c in dup_keys.values() if c > 1) == 3
    alloc = Counter()
    for row in t["tip_allocations"]:
        alloc[row["tip_id"]] += row["amount"]
    recs = [an.TipRec(r["id"], r["day"], r["total_amount"], alloc[r["id"]]) for r in t["tips"]]
    assert len(an.tip_mismatches(recs)) == 2


def test_ravi_scenario() -> None:
    gt = generate(42).ground_truth
    ravi = gt["ravi_kumar_last_week_vs_previous"]
    assert ravi["net_delta"].startswith("-₹")
    assert "2 fewer shifts" in ravi["changes"][0]["reason"]
    assert any(c["component"] == "deduction_uniform" for c in ravi["changes"])


def test_ambiguous_names_exist() -> None:
    names = {e["name"] for e in generate(42).tables["employees"]}
    assert {"Ravi Kumar", "Ravi K"} <= names


def test_policy_chunking() -> None:
    chunks = chunk_markdown((POLICY_DIR / "handbook.md").read_text(encoding="utf-8"))
    assert len(chunks) > 15
    assert any("Overtime rate" in c.section for c in chunks)
    assert all(len(c.text.split()) <= 300 for c in chunks)
