"""remove medicos and fks

Revision ID: 9b8eeee64818
Revises: 0ca913e9e6b5
Create Date: 2026-07-15

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9b8eeee64818'
down_revision: Union[str, None] = '0ca913e9e6b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop FK constraint and medico_id column from resultados first
    op.drop_index('ix_resultados_medico_id', table_name='resultados', if_exists=True)
    with op.batch_alter_table('resultados') as batch_op:
        try:
            batch_op.drop_constraint('fk_resultados_medico_id_medicos', type_='foreignkey')
        except Exception:
            pass
        try:
            batch_op.drop_column('medico_id')
        except Exception:
            pass

    # Drop medicos table
    op.drop_index('ix_medicos_cedula', table_name='medicos', if_exists=True)
    op.drop_index('ix_medicos_id', table_name='medicos', if_exists=True)
    op.drop_table('medicos', if_exists=True)


def downgrade() -> None:
    # Recreate medicos table
    op.create_table(
        'medicos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('cedula', sa.String(), nullable=False),
        sa.Column('nombre', sa.String(), nullable=False),
        sa.Column('apellido', sa.String(), nullable=True),
        sa.Column('especialidad', sa.String(), nullable=True),
        sa.Column('telefono', sa.String(), nullable=True),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_medicos'))
    )
    op.create_index(op.f('ix_medicos_id'), 'medicos', ['id'], unique=False)
    op.create_index(op.f('ix_medicos_cedula'), 'medicos', ['cedula'], unique=True)
