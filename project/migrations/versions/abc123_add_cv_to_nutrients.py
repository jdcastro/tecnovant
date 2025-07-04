"""add cv column to nutrients

Revision ID: abc123
Revises: b1d3f9c38b9c
Create Date: 2025-06-09 07:00:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'abc123'
down_revision = 'b1d3f9c38b9c'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('nutrients', sa.Column('cv', sa.Float(), nullable=True))


def downgrade():
    op.drop_column('nutrients', 'cv')
