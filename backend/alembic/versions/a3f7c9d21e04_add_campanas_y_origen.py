"""Add campanas, campana_pacientes, and origen to pacientes

Revision ID: a3f7c9d21e04
Revises: 6bcb55904e44
Create Date: 2026-09-07 14:37:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3f7c9d21e04'
down_revision: Union[str, None] = '6bcb55904e44'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- Tabla campanas ---
    op.create_table(
        'campanas',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('nombre', sa.String(), nullable=False),
        sa.Column('slug', sa.String(), nullable=False),
        sa.Column('tipo', sa.String(), nullable=False),
        sa.Column('descripcion', sa.String(), nullable=True),
        sa.Column('fecha_inicio', sa.Date(), nullable=True),
        sa.Column('fecha_fin', sa.Date(), nullable=True),
        sa.Column('ubicacion', sa.String(), nullable=True),
        sa.Column('direccion', sa.String(), nullable=True),
        sa.Column('estado', sa.String(), server_default='activa'),
        sa.Column('lat', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('lon', sa.Numeric(precision=9, scale=6), nullable=True),
        sa.Column('metadata_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_campanas_id', 'campanas', ['id'])
    op.create_index('ix_campanas_slug', 'campanas', ['slug'], unique=True)

    # --- Tabla campana_pacientes ---
    op.create_table(
        'campana_pacientes',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('campana_id', sa.Integer(), sa.ForeignKey('campanas.id'), nullable=False),
        sa.Column('paciente_id', sa.Integer(), sa.ForeignKey('pacientes.id'), nullable=False),
        sa.Column('fecha_inscripcion', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column('fuente_registro', sa.String(), server_default='manual'),
        sa.Column('datos_contextuales', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint('campana_id', 'paciente_id', name='uq_campana_paciente')
    )
    op.create_index('ix_campana_pacientes_id', 'campana_pacientes', ['id'])
    op.create_index('idx_campana_pacientes_campana', 'campana_pacientes', ['campana_id'])
    op.create_index('ix_campana_pacientes_paciente', 'campana_pacientes', ['paciente_id'])

    # --- Agregar columna origen a pacientes ---
    with op.batch_alter_table('pacientes') as batch_op:
        batch_op.add_column(sa.Column('origen', sa.String(), server_default='servicio_externo', nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('pacientes') as batch_op:
        batch_op.drop_column('origen')

    op.drop_table('campana_pacientes')
    op.drop_table('campanas')
