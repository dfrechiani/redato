"""m4 missoes table and atividade fk

Revision ID: fbd82380d452
Revises: b8d85498ffd3
Create Date: 2026-04-27 16:06:22.418064

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fbd82380d452'
down_revision: Union[str, Sequence[str], None] = 'b8d85498ffd3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema.

    Nota sobre `atividades.missao_id`: era VARCHAR(32) com CHECK enum
    em M1. Agora vira FK pra `missoes.id` (UUID). Em ambiente de
    DESENVOLVIMENTO local sem atividades reais, a conversão de tipo
    funciona direto. Em produção com dados, é necessário:
    1. Popular `missoes` (via seed_missoes) ANTES desta migration.
    2. Adicionar coluna temporária `missao_id_uuid` UUID nullable.
    3. UPDATE atividades SET missao_id_uuid = (SELECT id FROM missoes
       WHERE codigo = atividades.missao_id).
    4. Drop missao_id antigo + rename + add NOT NULL + FK.
    Documentado em portal/README.md.
    """
    op.create_table('missoes',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('codigo', sa.String(length=32), nullable=False),
    sa.Column('serie', sa.String(length=2), nullable=False),
    sa.Column('oficina_numero', sa.Integer(), nullable=False),
    sa.Column('titulo', sa.String(length=120), nullable=False),
    sa.Column('modo_correcao', sa.String(length=32), nullable=False),
    sa.Column('ativa', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
    sa.CheckConstraint("modo_correcao IN ('foco_c3', 'foco_c4', 'foco_c5', 'completo_parcial', 'completo')", name='ck_missao_modo_correcao'),
    sa.CheckConstraint("serie IN ('1S', '2S', '3S')", name='ck_missao_serie'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_missoes_codigo'), 'missoes', ['codigo'], unique=True)
    op.add_column('atividades', sa.Column('notificacao_enviada_em', sa.DateTime(timezone=True), nullable=True))
    # M4: missao_id passa de VARCHAR pra UUID. Removemos o CHECK
    # constraint antigo (string-based) e o índice composto antigo
    # (que referenciava missao_id do tipo errado), depois trocamos
    # o tipo via USING NULL (assume tabela atividades vazia em dev).
    op.drop_constraint('ck_atividade_missao_em_whitelist',
                       'atividades', type_='check')
    op.drop_index('ix_atividade_turma_missao_inicio', table_name='atividades')
    op.execute(
        "ALTER TABLE atividades "
        "ALTER COLUMN missao_id TYPE uuid USING NULL"
    )
    op.create_index(op.f('ix_atividades_missao_id'),
                    'atividades', ['missao_id'], unique=False)
    op.create_index('ix_atividade_turma_missao_inicio',
                    'atividades', ['turma_id', 'missao_id', 'data_inicio'])
    op.create_foreign_key('fk_atividades_missao', 'atividades',
                          'missoes', ['missao_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema. Não preserva atividades existentes — assume
    que rollback é em ambiente vazio."""
    op.drop_constraint('fk_atividades_missao', 'atividades',
                       type_='foreignkey')
    op.drop_index('ix_atividade_turma_missao_inicio', table_name='atividades')
    op.drop_index(op.f('ix_atividades_missao_id'), table_name='atividades')
    op.execute(
        "ALTER TABLE atividades "
        "ALTER COLUMN missao_id TYPE varchar(32) USING NULL"
    )
    op.create_index('ix_atividade_turma_missao_inicio',
                    'atividades', ['turma_id', 'missao_id', 'data_inicio'])
    op.create_check_constraint(
        'ck_atividade_missao_em_whitelist', 'atividades',
        "missao_id IN ('RJ1·OF10·MF', 'RJ1·OF11·MF', 'RJ1·OF12·MF', "
        "'RJ1·OF13·MF', 'RJ1·OF14·MF')",
    )
    op.drop_column('atividades', 'notificacao_enviada_em')
    op.drop_index(op.f('ix_missoes_codigo'), table_name='missoes')
    op.drop_table('missoes')
