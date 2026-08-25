"""Initial schema

Revision ID: sample
Revises:
Create Date: 2026-05-15 03:00:00.000000
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = 'sample'
down_revision = None


def upgrade() -> None:
    op.create_table('users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(255), nullable=False, unique=True),
        sa.Column('role', sa.Enum('admin', 'editor', 'viewer'), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table('users')
