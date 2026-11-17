"""Add examenes_orina (Examen General de Orina capturado por el químico)

Revision ID: d4a8b2c6e910
Revises: c7e2f1a9b304
Create Date: 2026-11-17 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a8b2c6e910'
down_revision: Union[str, None] = 'c7e2f1a9b304'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CAMPOS_TEXTO = [
    'color', 'aspecto',
    'glucosa', 'bilirrubina', 'cetonas', 'densidad', 'sangre', 'ph', 'proteinas',
    'urobilinogeno', 'nitritos', 'leucocitos_esterasa',
    'bacterias', 'celulas_epiteliales', 'leucocitos_campo',
]


def upgrade() -> None:
    # El arranque del backend ejecuta create_all, que ya pudo haber creado la tabla: la migración es idempotente.
    if sa.inspect(op.get_bind()).has_table('examenes_orina'):
        return
    op.create_table(
        'examenes_orina',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('paciente_id', sa.Integer(), sa.ForeignKey('pacientes.id'), nullable=False),
        sa.Column('fecha_toma', sa.Date(), nullable=False),
        *[sa.Column(c, sa.String(), nullable=True) for c in CAMPOS_TEXTO],
        sa.Column('quimico_fuente', sa.String(), nullable=True),
        sa.Column('sedimento', sa.Text(), nullable=True),
        sa.Column('observaciones', sa.Text(), nullable=True),
        sa.Column('quimico_id', sa.Integer(), sa.ForeignKey('quimicos.id'), nullable=True),
        sa.Column('capturado_por', sa.Integer(), sa.ForeignKey('usuarios.id'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint('paciente_id', 'fecha_toma', name='uq_examen_orina_paciente_fecha'),
    )
    op.create_index('ix_examenes_orina_id', 'examenes_orina', ['id'])
    op.create_index('ix_examenes_orina_paciente_id', 'examenes_orina', ['paciente_id'])


def downgrade() -> None:
    op.drop_table('examenes_orina')
