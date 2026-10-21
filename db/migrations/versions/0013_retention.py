"""Retention support (architecture v3 section 25).

- schedule_versions.discarded_at: discarded drafts are purged 7 days after they were discarded, not
  after they were created.
- version_shifts of a discarded version may be deleted (by the retention job). Published and superseded
  shift content stays immutable; drafts stay editable.

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0013"
down_revision: str | Sequence[str] | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

GUARD = """
CREATE OR REPLACE FUNCTION version_shifts_draft_only() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE st text;
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        SELECT status INTO st FROM schedule_versions WHERE id = OLD.version_id;
        IF st IS DISTINCT FROM 'draft' AND NOT (TG_OP = 'DELETE' AND st = 'discarded') THEN
            RAISE EXCEPTION 'schedule version % is %; its shifts are immutable', OLD.version_id, st
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    IF TG_OP IN ('INSERT', 'UPDATE') THEN
        SELECT status INTO st FROM schedule_versions WHERE id = NEW.version_id;
        IF st IS DISTINCT FROM 'draft' THEN
            RAISE EXCEPTION 'schedule version % is %; its shifts are immutable', NEW.version_id, st
                USING ERRCODE = 'check_violation';
        END IF;
    END IF;
    RETURN COALESCE(NEW, OLD);
END $$;
"""


def upgrade() -> None:
    op.add_column("schedule_versions", sa.Column("discarded_at", sa.DateTime(timezone=True), nullable=True))
    # Before this revision the discard time was not recorded; the creation time is the safe lower bound.
    op.execute("ALTER TABLE schedule_versions DISABLE TRIGGER schedule_versions_transitions")
    op.execute("UPDATE schedule_versions SET discarded_at = created_at WHERE status = 'discarded'")
    op.execute("ALTER TABLE schedule_versions ENABLE TRIGGER schedule_versions_transitions")
    op.execute(GUARD)


def downgrade() -> None:
    op.execute(GUARD.replace(" AND NOT (TG_OP = 'DELETE' AND st = 'discarded')", ""))
    op.drop_column("schedule_versions", "discarded_at")
