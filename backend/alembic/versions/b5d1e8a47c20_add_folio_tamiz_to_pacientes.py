"""Add folio_tamiz to pacientes (integración con tamiz-escolar)

Revision ID: b5d1e8a47c20
Revises: a3f7c9d21e04
Create Date: 2026-10-28 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5d1e8a47c20'
down_revision: Union[str, None] = 'a3f7c9d21e04'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('pacientes') as batch_op:
        batch_op.add_column(sa.Column('folio_tamiz', sa.String(), nullable=True))
    op.create_index('ix_pacientes_folio_tamiz', 'pacientes', ['folio_tamiz'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_pacientes_folio_tamiz', table_name='pacientes')
    with op.batch_alter_table('pacientes') as batch_op:
        batch_op.drop_column('folio_tamiz')
