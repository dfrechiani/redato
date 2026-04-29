"""envios tentativa_n

Adiciona coluna `tentativa_n` em `envios` e relaxa a constraint
única pra permitir múltiplas tentativas do mesmo aluno na mesma
atividade (cada uma com `tentativa_n` distinto).

Bug em prod (M9.6, 2026-04-29): aluno escolhia "2 — reavaliar como
nova tentativa" no fluxo de duplicata e bot processava nova
correção, mas:
- SQLite legado salvava a interaction nova
- Postgres `INSERT INTO envios` falhava com IntegrityError
  (`uq_envio_atividade_aluno`) porque já tinha envio antigo
- Erro era engolido como WARNING silencioso → dashboard do
  professor continuava apontando pra interaction velha
- Tentativas posteriores ficavam órfãs em `interactions`
  (sem envio apontando)

Fix:
- ADD `tentativa_n INTEGER NOT NULL DEFAULT 1` (backfill 1 em todas
  as rows existentes — eram única tentativa por design anterior)
- DROP `uq_envio_atividade_aluno` (atividade_id, aluno_turma_id)
- ADD `uq_envio_atividade_aluno_tentativa`
  (atividade_id, aluno_turma_id, tentativa_n)

Reconciliação dos órfãos pré-existentes (interactions sem envio
em prod) fica em script separado:
  scripts/reconciliar_envios_orfaos.py

Revision ID: g0a1b2c3d4e5
Revises: f0a1b2c3d4e5
Create Date: 2026-04-29 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'g0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'f0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ADD tentativa_n + recria UNIQUE constraint."""
    # 1. Adiciona coluna com default 1 (backfill automático)
    op.add_column(
        "envios",
        sa.Column(
            "tentativa_n",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    # 2. Drop constraint antiga
    op.drop_constraint(
        "uq_envio_atividade_aluno", "envios", type_="unique",
    )
    # 3. Cria constraint nova incluindo tentativa_n
    op.create_unique_constraint(
        "uq_envio_atividade_aluno_tentativa", "envios",
        ["atividade_id", "aluno_turma_id", "tentativa_n"],
    )


def downgrade() -> None:
    """Reverte. Falha se houver alguma row com tentativa_n > 1
    (perda de dado intencional — caller decide o que fazer)."""
    bind = op.get_bind()
    n_extras = bind.execute(
        sa.text("SELECT COUNT(*) FROM envios WHERE tentativa_n > 1")
    ).scalar()
    if n_extras and n_extras > 0:
        raise RuntimeError(
            f"downgrade abortado: {n_extras} envios com tentativa_n > 1. "
            "Esses dados serão perdidos pela constraint antiga "
            "(UNIQUE atividade_id+aluno_turma_id). Remova-os manualmente "
            "antes de prosseguir."
        )
    op.drop_constraint(
        "uq_envio_atividade_aluno_tentativa", "envios", type_="unique",
    )
    op.create_unique_constraint(
        "uq_envio_atividade_aluno", "envios",
        ["atividade_id", "aluno_turma_id"],
    )
    op.drop_column("envios", "tentativa_n")
