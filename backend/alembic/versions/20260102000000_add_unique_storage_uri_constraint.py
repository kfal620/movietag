"""add unique storage_uri constraint

Revision ID: 20260102000000
Revises: fd90a9bbb087
Create Date: 2025-12-29 15:14:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260102000000'
down_revision = 'fd90a9bbb087'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add unique constraint on storage_uri
    # This prevents importing the same frame multiple times
    op.create_unique_constraint(
        'uq_frames_storage_uri',
        'frames',
        ['storage_uri']
    )


def downgrade() -> None:
    # Remove unique constraint
    op.drop_constraint('uq_frames_storage_uri', 'frames', type_='unique')
