"""B5.4 (architecture v3 section 19): the fixed employee CSV template is parsed and validated."""

from __future__ import annotations

import uuid

from importer import employees_csv as csvi

IND, KOR = uuid.uuid4(), uuid.uuid4()
GRILL, PREP = uuid.uuid4(), uuid.uuid4()
OUTLETS = {"indiranagar": IND, "ind": IND, "koramangala": KOR}
SKILLS = {"grill": GRILL, "prep": PREP}
HEADER = ",".join(csvi.COLUMNS)
DAYS_OFF = "," * 13  # fourteen empty day cells


def parse(
    *lines: str, existing: set[tuple[uuid.UUID, str]] | None = None
) -> tuple[list[str], list[csvi.Row]]:
    return csvi.parse("\n".join([HEADER, *lines]), outlets=OUTLETS, skills=SKILLS, existing=existing or set())


def test_the_template_example_is_valid() -> None:
    problems, [row] = parse(csvi.EXAMPLE)
    assert problems == [] and row.valid, row.errors
    assert (row.name, row.outlet_id, set(row.skill_ids)) == ("Asha Nair", IND, {GRILL, PREP})
    assert (row.hourly_rate_paise, row.max_weekly_minutes, row.preferred_weekly_minutes) == (
        19000,
        2880,
        2400,
    )
    assert row.windows[0] == (0, 600, 1320) and len(row.windows) == 5  # Wednesday and Sunday off


def test_overnight_windows_and_outlet_slugs() -> None:
    _, [row] = parse("Ravi,IND,grill,150.50,40,," + ",".join(["18:00", "02:00"] + [""] * 12))
    assert row.valid and row.hourly_rate_paise == 15050 and row.windows == [(0, 1080, 1560)]


def test_every_error_is_reported_per_column() -> None:
    _, [row] = parse("," + "Mars,Grill;Juggling,-5,99,100," + "10:15,22:00" + "," * 12)
    columns = {c for c, _ in row.errors}
    expected = {"name", "outlet", "skills", "hourly_rate", "max_weekly_hours", "preferred_weekly_hours"}
    assert columns == expected | {"mon_start"}
    assert not row.valid


def test_duplicates_within_the_file_and_against_existing_staff() -> None:
    line = "Neha Iyer,Indiranagar,Grill,180,48,," + DAYS_OFF
    _, rows = parse(line, line, existing=set())
    assert rows[0].valid and rows[1].errors == [("name", "Duplicate of row 2.")]
    _, [again] = parse(line, existing={(IND, "neha iyer")})
    assert again.errors and again.errors[0][0] == "name"


def test_header_and_size_limits() -> None:
    problems, rows = csvi.parse("name,outlet\nx,y", outlets=OUTLETS, skills=SKILLS, existing=set())
    assert rows == [] and problems[0].startswith("Missing columns")
    assert csvi.parse("", outlets=OUTLETS, skills=SKILLS, existing=set())[0]
    many = [f"P{i},Indiranagar,Grill,100,40,," + DAYS_OFF for i in range(csvi.MAX_ROWS + 1)]
    assert parse(*many)[0] == [f"At most {csvi.MAX_ROWS} employees per import."]
    _, [short] = parse("Only,three,cells")
    assert short.errors[0][0] == "*"
