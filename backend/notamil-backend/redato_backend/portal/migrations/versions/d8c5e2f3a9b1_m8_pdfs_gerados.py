"""m8 pdfs gerados

Tabela `pdfs_gerados` pra histórico de PDFs renderizados pelo portal.

Revision ID: d8c5e2f3a9b1
Revises: c7e4a9b1d3f2
Create Date: 2026-04-27 21:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd8c5e2f3a9b1'
down_revision: Union[str, Sequence[str], None] = 'c7e4a9b1d3f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pdfs_gerados',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('tipo', sa.String(length=32), nullable=False),
        sa.Column('escopo_id', sa.UUID(), nullable=False),
        sa.Column('escola_id', sa.UUID(), nullable=False),
        sa.Column('gerado_por_user_id', sa.UUID(), nullable=False),
        sa.Column('gerado_em', sa.DateTime(timezone=True), nullable=False),
        sa.Column('arquivo_path', sa.String(length=255), nullable=False),
        sa.Column('tamanho_bytes', sa.Integer(), nullable=False),
        sa.Column('parametros', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['escola_id'], ['escolas.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.CheckConstraint(
            "tipo IN ('dashboard_turma', 'dashboard_escola', "
            "'evolucao_aluno', 'atividade_detalhe')",
            name='ck_pdf_tipo_em_set',
        ),
    )
    op.create_index('ix_pdfs_gerados_escola_id',
                    'pdfs_gerados', ['escola_id'], unique=False)
    op.create_index('ix_pdfs_gerados_escopo_id',
                    'pdfs_gerados', ['escopo_id'], unique=False)
    op.create_index('ix_pdf_escopo_tipo_gerado',
                    'pdfs_gerados',
                    ['escopo_id', 'tipo', 'gerado_em'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_pdf_escopo_tipo_gerado', table_name='pdfs_gerados')
    op.drop_index('ix_pdfs_gerados_escopo_id', table_name='pdfs_gerados')
    op.drop_index('ix_pdfs_gerados_escola_id', table_name='pdfs_gerados')
    op.drop_table('pdfs_gerados')
