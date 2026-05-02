"""professor telefone + lgpd

Adiciona 3 colunas em `professores` pra suportar o dashboard via
WhatsApp (PROMPT 1/2 — infra de auth + aviso LGPD):

- `telefone` (varchar 20, nullable): telefone E.164 do professor
  vinculado pro acesso via WhatsApp.
- `telefone_verificado_em` (timestamptz, nullable): preenchido no
  momento que o portal grava o telefone (PATCH /auth/perfil/telefone).
- `lgpd_aceito_em` (timestamptz, nullable): preenchido quando o
  professor responde "sim" no WhatsApp ao aviso de LGPD. Campo é
  null até o aceite — sem aceite, bot não responde com dados.

Constraint:
- Índice único parcial em `telefone` WHERE telefone IS NOT NULL —
  garante que nenhum telefone está em 2 contas (mas NULL pode se
  repetir, claro).

NÃO toca em alunos_turma — alunos continuam tendo telefone próprio
em alunos_turma.telefone, sem conflito (lookup do bot é por table:
primeiro tenta professor, depois aluno).

Revision ID: i0a1b2c3d4e5
Revises: h0a1b2c3d4e5
Create Date: 2026-05-02 11:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'i0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'h0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ADD telefone + telefone_verificado_em + lgpd_aceito_em em
    professores + índice único parcial em telefone."""
    op.add_column(
        "professores",
        sa.Column("telefone", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "professores",
        sa.Column(
            "telefone_verificado_em",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "professores",
        sa.Column(
            "lgpd_aceito_em",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Índice único PARCIAL: aceita N nulls, recusa duplicação de
    # telefone preenchido. Postgres `WHERE` em CREATE INDEX é
    # nativo — não precisa de extension.
    op.create_index(
        "uq_professor_telefone_quando_setado",
        "professores",
        ["telefone"],
        unique=True,
        postgresql_where=sa.text("telefone IS NOT NULL"),
    )


def downgrade() -> None:
    """Reverte: drop do índice + 3 colunas. Falha se houver
    professor com lgpd_aceito_em != NULL — perda de aceite LGPD
    é sensível (audit trail), caller decide se aceita."""
    bind = op.get_bind()
    n_aceites = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM professores "
            "WHERE lgpd_aceito_em IS NOT NULL"
        )
    ).scalar()
    if n_aceites and n_aceites > 0:
        raise RuntimeError(
            f"downgrade abortado: {n_aceites} professor(es) com "
            "lgpd_aceito_em preenchido. Drop apaga o registro de "
            "consentimento LGPD — sensível pra audit. Limpe "
            "manualmente antes de prosseguir."
        )
    op.drop_index(
        "uq_professor_telefone_quando_setado", table_name="professores",
    )
    op.drop_column("professores", "lgpd_aceito_em")
    op.drop_column("professores", "telefone_verificado_em")
    op.drop_column("professores", "telefone")
