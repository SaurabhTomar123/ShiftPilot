"""The stored run input must reproduce the snapshot exactly (the worker solves from it alone)."""

from __future__ import annotations

import json
import uuid
from datetime import timedelta

import pytest

from scheduling import snapshot_json
from scheduling.model import Absence, Shift
from seed import world
from tests.world_snapshot import build


def rich_snapshot():  # type: ignore[no-untyped-def]
    ravi, arjun = world.uid("employee", "ravi"), world.uid("employee", "arjun")
    day = world.NEXT_WEEK + timedelta(days=2)
    other = world.uid("outlet", "koramangala")
    lock = Shift(
        uuid.uuid4(),
        world.uid("outlet", "indiranagar"),
        ravi,
        world.SKILL["Grill"],
        world.at(day, 600),
        world.at(day, 1080),
        30,
        world.at(day, 930),
        True,
    )
    busy = Shift(uuid.uuid4(), other, arjun, world.SKILL["Grill"], world.at(day, 600), world.at(day, 900))
    return build(
        base_locked={lock.logical_id: lock},
        commitments=(busy,),
        absences=(Absence(arjun, world.at(day, 0), world.at(day, 1440), "confirmed"),),
        travel_minutes={(lock.outlet_id, other): 35},
    )


def test_round_trip_is_exact() -> None:
    snap = rich_snapshot()
    doc = snapshot_json.dump(snap)
    assert snapshot_json.load(json.loads(json.dumps(doc))) == snap


def test_digest_is_stable_and_sensitive() -> None:
    doc = snapshot_json.dump(rich_snapshot())
    assert snapshot_json.digest(doc) == snapshot_json.digest(json.loads(json.dumps(doc)))
    changed = {**doc, "policy": {**doc["policy"], "min_rest_minutes": 601}}
    assert snapshot_json.digest(changed) != snapshot_json.digest(doc)


def test_unknown_schema_versions_are_refused() -> None:
    with pytest.raises(ValueError):
        snapshot_json.load({**snapshot_json.dump(build()), "snapshot_schema_version": 99})
