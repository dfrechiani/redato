"""m6 sessoes invalidadas em

Adiciona `sessoes_invalidadas_em` em coordenadores e professores pra
suportar "sair de todas as sessões" (M6). Middleware rejeita tokens
com iat < sessoes_invalidadas_em.

Revision ID: c7e4a9b1d3f2
Revises: fbd82380d452
Create Date: 2026-04-27 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7e4a9b1d3f2'
down_revision: Union[str, Sequence[str], None] = 'fbd82380d452'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'coordenadores',
        sa.Column('sessoes_invalidadas_em', sa.DateTime(timezone=True),
                  nullable=True),
    )
    op.add_column(
        'professores',
        sa.Column('sessoes_invalidadas_em', sa.DateTime(timezone=True),
                  nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('professores', 'sessoes_invalidadas_em')
    op.drop_column('coordenadores', 'sessoes_invalidadas_em')
