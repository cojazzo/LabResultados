"""add_geocoords_to_pacientes

Revision ID: 0ca913e9e6b5
Revises: 14c203bef772
Create Date: 2026-07-15 14:03:47.821372

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0ca913e9e6b5'
down_revision: Union[str, Sequence[str], None] = '14c203bef772'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Agrega columnas lat, lon y geocoded_at a la tabla pacientes."""
    with op.batch_alter_table('pacientes', schema=None) as batch_op:
        batch_op.add_column(sa.Column('lat', sa.Numeric(precision=9, scale=6), nullable=True))
        batch_op.add_column(sa.Column('lon', sa.Numeric(precision=9, scale=6), nullable=True))
        batch_op.add_column(sa.Column('geocoded_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Elimina las columnas de geocoordinadas."""
    with op.batch_alter_table('pacientes', schema=None) as batch_op:
        batch_op.drop_column('geocoded_at')
        batch_op.drop_column('lon')
        batch_op.drop_column('lat')
