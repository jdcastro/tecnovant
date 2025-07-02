"""add nutrient cv table

Revision ID: 0c3b450fe21f
Revises: b1d3f9c38b9c
Create Date: 2025-07-02 20:40:00.000000
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0c3b450fe21f'
down_revision = 'b1d3f9c38b9c'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'nutrient_cvs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('nutrient_id', sa.Integer(), nullable=False),
        sa.Column('cv', sa.Numeric(5, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['nutrient_id'], ['nutrients.id'], ),
        sa.UniqueConstraint('nutrient_id', name='uq_nutrient_cv_nutrient_id'),
    )


def downgrade():
    op.drop_table('nutrient_cvs')
