"""add optional fields to organization

Revision ID: b1d3f9c38b9c
Revises: 
Create Date: 2025-06-09 07:06:59.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b1d3f9c38b9c'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('organizations', sa.Column('nit', sa.String(length=50), nullable=True))
    op.add_column('organizations', sa.Column('contact', sa.String(length=100), nullable=True))
    op.add_column('organizations', sa.Column('address', sa.String(length=150), nullable=True))
    op.add_column('organizations', sa.Column('phone', sa.String(length=50), nullable=True))


def downgrade():
    op.drop_column('organizations', 'phone')
    op.drop_column('organizations', 'address')
    op.drop_column('organizations', 'contact')
    op.drop_column('organizations', 'nit')
