"""phase4 alert ingestion correlation fields

Revision ID: 4a365bafd615
Revises: 68f31eee722e
Create Date: 2026-08-02 01:40:25.456433

IMPORTANT (read before running):
This migration was generated and verified against a reconstructed
Phase 1-3 schema in a sandbox, since the real alerts table (as it
exists in your actual repo) wasn't available to diff against directly.

Before running `alembic upgrade head`:
1. Run `alembic heads` in your real project to find your current head
   revision id (should be whatever Phase 3's last migration is).
2. Replace 68f31eee722e below with that id.
3. Confirm your real `alerts` table does NOT already have columns named
   raw_payload, extracted_indicators, or correlation_score -- if it
   does (e.g. you already added something similar), this migration
   will fail with a "column already exists" error and needs adjusting
   rather than being applied as-is.

This migration was verified end-to-end in a live Postgres 16 instance,
including against an `alerts` table with a pre-existing row, to confirm
the NOT NULL backfill (see upgrade() below) doesn't break on real data,
and including a full downgrade -> upgrade cycle.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4a365bafd615'
down_revision: Union[str, Sequence[str], None] = '68f31eee722e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    NOTE: manually adjusted from the raw autogenerate output. These three
    columns are NOT NULL at the model level, so if the `alerts` table
    already has rows (e.g. from earlier phase testing) a plain
    `add_column(..., nullable=False)` would fail with a NOT NULL
    violation. Adding a server_default lets existing rows backfill
    cleanly; the defaults are then dropped so future inserts must supply
    real values via the application (matching the SQLAlchemy model,
    which sets Python-side defaults rather than relying on the DB).
    """
    op.add_column(
        'alerts',
        sa.Column(
            'raw_payload',
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        'alerts',
        sa.Column(
            'extracted_indicators',
            postgresql.ARRAY(sa.String()),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )
    op.add_column(
        'alerts',
        sa.Column(
            'correlation_score',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )

    # Drop the server defaults now that existing rows are backfilled --
    # going forward the application supplies these values explicitly.
    op.alter_column('alerts', 'raw_payload', server_default=None)
    op.alter_column('alerts', 'extracted_indicators', server_default=None)
    op.alter_column('alerts', 'correlation_score', server_default=None)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('alerts', 'correlation_score')
    op.drop_column('alerts', 'extracted_indicators')
    op.drop_column('alerts', 'raw_payload')
