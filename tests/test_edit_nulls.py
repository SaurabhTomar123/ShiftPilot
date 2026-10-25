"""An update echoed back with every field present keeps what it does not change (Codex 3.19 flow)."""

from __future__ import annotations

import uuid

from api.v2 import drafts
from api.v2 import schemas as s


def test_null_keeps_values_except_the_assignee() -> None:
    lid, emp = uuid.uuid4(), uuid.uuid4()
    full = s.EditRequest.model_validate(
        {
            "expected_revision": 1,
            "edits": [
                {
                    "op": "update",
                    "logical_shift_id": str(lid),
                    "employee_id": str(emp),
                    "skill_id": None,
                    "start_at": None,
                    "end_at": None,
                    "break_start_at": None,
                    "break_minutes": None,
                },
                {"op": "update", "logical_shift_id": str(lid), "employee_id": None},
            ],
        }
    )
    reassign, unassign = drafts._to_edits(full)
    assert reassign.fields == {"employee_id": emp}
    assert unassign.fields == {"employee_id": None}
