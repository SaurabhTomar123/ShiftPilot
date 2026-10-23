"""A3.11 (architecture v3 sections 6 and 42): the scheduling engine is pure.

The solver, validator, metrics, repair and explanation builder, edits, diffs, demand expansion and the
snapshot codec may import only the standard library, OR-Tools and each other: no database, HTTP, web
framework or API-schema code. Only snapshot_db (loads a snapshot) and worker (runs jobs) touch the
database. This is an allowlist, so a new third-party import fails here until it is deliberately allowed.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1] / "scheduling"
PURE = {
    "model",
    "solver",
    "validator",
    "metrics",
    "repair",
    "edits",
    "diff",
    "demand",
    "snapshot_json",
    "rules",
    "fairness",
    "freeze",
    "trace",
    "portfolio",
}
ADAPTERS = {"snapshot_db", "worker"}  # allowed to touch the database; nothing pure may import them
THIRD_PARTY = {"ortools"}


def imports(module: str) -> set[str]:
    tree = ast.parse((ROOT / f"{module}.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module == "scheduling":  # from scheduling import solver, validator
                found |= {f"scheduling.{alias.name}" for alias in node.names}
            else:
                found.add(node.module)
        elif isinstance(node, ast.ImportFrom) and node.level:
            found |= {f"scheduling.{node.module or alias.name}" for alias in node.names}
    return found


def test_every_scheduling_module_is_classified() -> None:
    modules = {p.stem for p in ROOT.glob("*.py")} - {"__init__"}
    assert modules == PURE | ADAPTERS, "classify new scheduling modules as pure or adapter"


@pytest.mark.parametrize("module", sorted(PURE))
def test_pure_modules_import_only_stdlib_ortools_and_each_other(module: str) -> None:
    bad = []
    for name in imports(module):
        root = name.split(".")[0]
        if root == "scheduling":
            if name.split(".")[1] not in PURE:
                bad.append(name)
        elif root not in sys.stdlib_module_names and root not in THIRD_PARTY and root != "__future__":
            bad.append(name)
    assert not bad, f"scheduling/{module}.py must stay pure but imports {sorted(bad)}"


def test_the_rule_catches_a_violation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Guard the guard: a database import in a pure module is reported."""
    (tmp_path / "solver.py").write_text("from sqlalchemy import text\nfrom scheduling import worker\n")
    monkeypatch.setattr(sys.modules[__name__], "ROOT", tmp_path)
    with pytest.raises(AssertionError, match="sqlalchemy"):
        test_pure_modules_import_only_stdlib_ortools_and_each_other("solver")
