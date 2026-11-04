"""Add peticiones (vínculo ID de petición del servicio externo -> paciente)

Revision ID: c7e2f1a9b304
Revises: b5d1e8a47c20
Create Date: 2026-11-04 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e2f1a9b304'
down_revision: Union[str, None] = 'b5d1e8a47c20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # El arranque del backend ejecuta create_all, que ya pudo haber creado la tabla: la migración es idempotente.
    if sa.inspect(op.get_bind()).has_table('peticiones'):
        return
    op.create_table(
        'peticiones',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('id_peticion', sa.String(), nullable=False),
        sa.Column('paciente_id', sa.Integer(), sa.ForeignKey('pacientes.id'), nullable=False),
        sa.Column('fuente', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index('ix_peticiones_id', 'peticiones', ['id'])
    op.create_index('ix_peticiones_id_peticion', 'peticiones', ['id_peticion'], unique=True)
    op.create_index('ix_peticiones_paciente_id', 'peticiones', ['paciente_id'])


def downgrade() -> None:
    op.drop_table('peticiones')
