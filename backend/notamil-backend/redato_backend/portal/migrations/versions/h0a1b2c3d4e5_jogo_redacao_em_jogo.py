"""jogo redacao em jogo - tabelas

Cria 5 tabelas pra suportar o jogo "Redação em Jogo" (Fase 2 passo 1):

1. `jogos_minideck` — catálogo dos 7 minidecks temáticos
   (saude_mental, inclusao_digital, etc.).
2. `cartas_estruturais` — 63 cartas E01-E63 com lacunas, COMPARTILHADAS
   entre todos os temas (frase com placeholders [PROBLEMA],
   [REPERTORIO], [PALAVRA_CHAVE], [AGENTE], [ACAO_MEIO]).
3. `cartas_lacuna` — cartas temáticas (P/R/K/A/AC/ME/F) que substituem
   os placeholders das estruturais. ~104 cartas por minideck.
4. `partidas_jogo` — instâncias de jogo dentro de uma atividade. FK
   `atividade_id` NÃO única (decisão G.1.2 do adendo de 2026-04-29):
   uma atividade pode ter múltiplas partidas (ex: 3 grupos da turma
   jogando paralelo).
5. `reescritas_individuais` — texto autoral de cada aluno do grupo
   sobre a redação cooperativa montada pela partida. UNIQUE
   (partida_id, aluno_turma_id) — 1 reescrita por aluno por partida.

Decisões pedagógicas que afetaram o schema:
- `partidas_jogo` 1:N com `atividades` (NÃO 1:1) — suporta múltiplos
  grupos jogando o mesmo tema na mesma turma simultaneamente.
- `reescritas_individuais.aluno_turma_id` referencia AlunoTurma direto
  (não Envio) porque o jogo é fluxo paralelo ao bot Redato — o aluno
  pode reescrever via portal sem WhatsApp.
- `cartas_estruturais.lacunas` é ARRAY(TEXT) Postgres — lista
  ordenada dos placeholders presentes no texto (extraída via regex
  pelo seed; coluna materializada pra evitar reparse a cada query).
- CHECK constraints em `secao` (cartas_estruturais) e `tipo`
  (cartas_lacuna) — barram inserts de valores não documentados na
  rubrica do jogo. Vão pegar erro de seed cedo, não em runtime.
- Catálogo (`cartas_estruturais` / `cartas_lacuna`) referenciado por
  partidas via JSONB de codigos — não FK direta, pra preservar a
  partida intacta se carta for editada/removida.

Revision ID: h0a1b2c3d4e5
Revises: g0a1b2c3d4e5
Create Date: 2026-04-29 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'h0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'g0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ──────────────────────────────────────────────────────────────────────
# Enums (em texto + CHECK constraint, não tipo ENUM nativo do Postgres
# pra simplificar drift entre dev/prod e evitar migration de ALTER TYPE
# quando rubrica adicionar seção/tipo novo).
# ──────────────────────────────────────────────────────────────────────

_SECOES_VALIDAS = (
    'ABERTURA', 'TESE',
    'TOPICO_DEV1', 'ARGUMENTO_DEV1', 'REPERTORIO_DEV1',
    'TOPICO_DEV2', 'ARGUMENTO_DEV2', 'REPERTORIO_DEV2',
    'RETOMADA', 'PROPOSTA',
)
_CORES_VALIDAS = ('AZUL', 'AMARELO', 'VERDE', 'LARANJA')
_TIPOS_LACUNA = (
    'PROBLEMA', 'REPERTORIO', 'PALAVRA_CHAVE',
    'AGENTE', 'ACAO', 'MEIO', 'FIM',
)


def _ck_in(values: tuple, col: str) -> str:
    """Helper SQL: 'col IN (\'A\',\'B\',\'C\')'."""
    quoted = ", ".join(f"'{v}'" for v in values)
    return f"{col} IN ({quoted})"


def upgrade() -> None:
    # ──────────────────────────────────────────────────────────────────
    # 1. jogos_minideck — catálogo dos temas
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "jogos_minideck",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                   primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tema", sa.Text(), nullable=False, unique=True),
        sa.Column("nome_humano", sa.Text(), nullable=False),
        sa.Column("serie", sa.Text(), nullable=True),
        sa.Column("descricao", sa.Text(), nullable=True),
        sa.Column("ativo", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
    )
    # `tema` já é UNIQUE (constraint), mas índice explícito ajuda
    # quando consulta usa LIKE/prefixo (futuro).
    op.create_index(
        "ix_jogos_minideck_tema", "jogos_minideck", ["tema"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 2. cartas_estruturais — 63 cartas E01-E63 (compartilhadas)
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "cartas_estruturais",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                   primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("codigo", sa.Text(), nullable=False, unique=True),
        sa.Column("secao", sa.Text(), nullable=False),
        sa.Column("cor", sa.Text(), nullable=False),
        sa.Column("texto", sa.Text(), nullable=False),
        # ARRAY Postgres — lista de placeholders (PROBLEMA, REPERTORIO,
        # PALAVRA_CHAVE, AGENTE, ACAO_MEIO) presentes em `texto`.
        # Materializada no seed pra render de UI não precisar reparsing.
        sa.Column(
            "lacunas",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("ARRAY[]::text[]"),
        ),
        sa.Column("ordem", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.CheckConstraint(
            _ck_in(_SECOES_VALIDAS, "secao"),
            name="ck_cartas_estruturais_secao",
        ),
        sa.CheckConstraint(
            _ck_in(_CORES_VALIDAS, "cor"),
            name="ck_cartas_estruturais_cor",
        ),
    )
    op.create_index(
        "ix_cartas_estruturais_codigo", "cartas_estruturais", ["codigo"],
    )
    op.create_index(
        "ix_cartas_estruturais_secao_ordem",
        "cartas_estruturais", ["secao", "ordem"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 3. cartas_lacuna — temáticas, agrupadas por minideck
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "cartas_lacuna",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                   primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "minideck_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jogos_minideck.id", name="fk_cartas_lacuna_minideck"),
            nullable=False,
        ),
        sa.Column("tipo", sa.Text(), nullable=False),
        sa.Column("codigo", sa.Text(), nullable=False),
        sa.Column("conteudo", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "minideck_id", "codigo",
            name="uq_cartas_lacuna_minideck_codigo",
        ),
        sa.CheckConstraint(
            _ck_in(_TIPOS_LACUNA, "tipo"),
            name="ck_cartas_lacuna_tipo",
        ),
    )
    op.create_index(
        "ix_cartas_lacuna_minideck_codigo",
        "cartas_lacuna", ["minideck_id", "codigo"],
    )
    op.create_index(
        "ix_cartas_lacuna_minideck_tipo",
        "cartas_lacuna", ["minideck_id", "tipo"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 4. partidas_jogo — instâncias de jogo
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "partidas_jogo",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                   primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "atividade_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("atividades.id", name="fk_partidas_jogo_atividade"),
            nullable=False,
        ),
        sa.Column(
            "minideck_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("jogos_minideck.id", name="fk_partidas_jogo_minideck"),
            nullable=False,
        ),
        sa.Column("grupo_codigo", sa.Text(), nullable=False),
        sa.Column(
            "cartas_escolhidas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("texto_montado", sa.Text(), nullable=False),
        sa.Column("prazo_reescrita", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "criada_por_professor_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("professores.id",
                           name="fk_partidas_jogo_professor"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        # NOTA: `atividade_id` SEM unique. Decisão G.1.2: 1:N suportado.
        # Composto (atividade_id, grupo_codigo) é o "natural key" — dois
        # grupos diferentes podem ter o mesmo nome em atividades
        # diferentes, mas dentro da mesma atividade os codes têm que
        # ser distintos (UI mostra "Grupo Azul / Grupo Verde / ...").
        sa.UniqueConstraint(
            "atividade_id", "grupo_codigo",
            name="uq_partidas_jogo_atividade_grupo",
        ),
    )
    op.create_index(
        "ix_partidas_jogo_atividade", "partidas_jogo", ["atividade_id"],
    )
    op.create_index(
        "ix_partidas_jogo_minideck", "partidas_jogo", ["minideck_id"],
    )

    # ──────────────────────────────────────────────────────────────────
    # 5. reescritas_individuais — uma por aluno por partida
    # ──────────────────────────────────────────────────────────────────
    op.create_table(
        "reescritas_individuais",
        sa.Column("id", postgresql.UUID(as_uuid=True),
                   primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "partida_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("partidas_jogo.id",
                           name="fk_reescritas_partida"),
            nullable=False,
        ),
        sa.Column(
            "aluno_turma_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alunos_turma.id",
                           name="fk_reescritas_aluno_turma"),
            nullable=False,
        ),
        sa.Column("texto", sa.Text(), nullable=False),
        sa.Column(
            "redato_output",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("elapsed_ms", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                   server_default=sa.text("now()")),
        sa.UniqueConstraint(
            "partida_id", "aluno_turma_id",
            name="uq_reescritas_partida_aluno",
        ),
    )
    op.create_index(
        "ix_reescritas_partida", "reescritas_individuais", ["partida_id"],
    )
    op.create_index(
        "ix_reescritas_aluno_turma",
        "reescritas_individuais", ["aluno_turma_id"],
    )


def downgrade() -> None:
    """DROP em ordem reversa de FK pra não pisar em constraint."""
    op.drop_index("ix_reescritas_aluno_turma", "reescritas_individuais")
    op.drop_index("ix_reescritas_partida", "reescritas_individuais")
    op.drop_table("reescritas_individuais")

    op.drop_index("ix_partidas_jogo_minideck", "partidas_jogo")
    op.drop_index("ix_partidas_jogo_atividade", "partidas_jogo")
    op.drop_table("partidas_jogo")

    op.drop_index("ix_cartas_lacuna_minideck_tipo", "cartas_lacuna")
    op.drop_index("ix_cartas_lacuna_minideck_codigo", "cartas_lacuna")
    op.drop_table("cartas_lacuna")

    op.drop_index("ix_cartas_estruturais_secao_ordem", "cartas_estruturais")
    op.drop_index("ix_cartas_estruturais_codigo", "cartas_estruturais")
    op.drop_table("cartas_estruturais")

    op.drop_index("ix_jogos_minideck_tema", "jogos_minideck")
    op.drop_table("jogos_minideck")
