"""extend modo_correcao foco_c1 c2

Adiciona `foco_c1` e `foco_c2` aos modos válidos de correção em
`missoes`. Necessário pra séries 2S e 3S, onde competências C1 e C2
viram foco de oficinas específicas.

Schema atual já permitia foco_c3, foco_c4, foco_c5, completo_parcial,
completo (isso vinha do M4). Agora estende sem mudar dados existentes.

Revision ID: e9f1c8a2b4d5
Revises: d8c5e2f3a9b1
Create Date: 2026-04-27 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e9f1c8a2b4d5'
down_revision: Union[str, Sequence[str], None] = 'd8c5e2f3a9b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Recria CHECK incluindo foco_c1 e foco_c2."""
    op.drop_constraint(
        "ck_missao_modo_correcao", "missoes", type_="check",
    )
    op.create_check_constraint(
        "ck_missao_modo_correcao", "missoes",
        "modo_correcao IN ('foco_c1', 'foco_c2', "
        "'foco_c3', 'foco_c4', 'foco_c5', "
        "'completo_parcial', 'completo')",
    )


def downgrade() -> None:
    """Volta CHECK ao set anterior. Bloqueia downgrade se houver
    missões usando foco_c1/foco_c2 — caller decide o que fazer."""
    op.drop_constraint(
        "ck_missao_modo_correcao", "missoes", type_="check",
    )
    op.create_check_constraint(
        "ck_missao_modo_correcao", "missoes",
        "modo_correcao IN ('foco_c3', 'foco_c4', 'foco_c5', "
        "'completo_parcial', 'completo')",
    )
