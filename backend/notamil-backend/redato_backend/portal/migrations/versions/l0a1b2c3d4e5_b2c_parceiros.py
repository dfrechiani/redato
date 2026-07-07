"""b2c parceiros — Correção {Parceiro} (influencers)

Cria as 5 tabelas do modo B2C por assinatura (SPEC_B2C_REDATO.md §3),
100% paralelas ao fluxo escola (B2G): nenhuma FK para
Escola/Turma/AlunoTurma/Envio/Atividade. Todo o módulo fica atrás da
flag REDATO_B2C_ENABLED — com a flag desligada, estas tabelas existem
mas nunca são lidas nem escritas.

Tabelas:
- parceiros_b2c   : professor-influencer + branding + config comercial
- alunos_b2c      : aluno que chegou pelo link (FSM por telefone)
- assinaturas_b2c : assinatura recorrente Asaas (com split)
- envios_b2c      : cada correção entregue (5 notas + diagnóstico)
- eventos_billing : idempotência dos webhooks do gateway

Revision ID: l0a1b2c3d4e5
Revises: k0a1b2c3d4e5
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "l0a1b2c3d4e5"
down_revision: Union[str, Sequence[str], None] = "k0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parceiros_b2c",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("slug", sa.String(64), nullable=False),
        sa.Column("codigo_entrada", sa.String(32), nullable=False),
        sa.Column("nome_publico", sa.String(120), nullable=False),
        sa.Column("nome_professor", sa.String(120), nullable=False),
        sa.Column("wallet_id_asaas", sa.String(64), nullable=True),
        sa.Column("share_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("preco_centavos", sa.Integer(), nullable=False,
                  server_default="3990"),
        sa.Column("ativo", sa.Boolean(), nullable=False,
                  server_default=sa.true()),
        sa.Column("branding", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "share_pct IS NULL OR (share_pct >= 0 AND share_pct <= 100)",
            name="ck_parceiro_b2c_share_pct_range",
        ),
        sa.CheckConstraint(
            "preco_centavos > 0", name="ck_parceiro_b2c_preco_positivo",
        ),
    )
    op.create_index("ix_parceiros_b2c_slug", "parceiros_b2c", ["slug"],
                    unique=True)
    op.create_index("ix_parceiros_b2c_codigo_entrada", "parceiros_b2c",
                    ["codigo_entrada"], unique=True)

    op.create_table(
        "alunos_b2c",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("telefone_e164", sa.String(20), nullable=False),
        sa.Column("nome", sa.String(255), nullable=True),
        sa.Column("parceiro_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("parceiros_b2c.id"), nullable=False),
        sa.Column("estado", sa.String(32), nullable=False,
                  server_default="novo"),
        sa.Column("cpf", sa.String(14), nullable=True),
        sa.Column("correcoes_gratis_usadas", sa.Integer(), nullable=False,
                  server_default="0"),
        sa.Column("consent_lgpd_at", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "estado IN ('novo','aguardando_nome','aguardando_cpf',"
            "'degustacao','aguardando_pagamento','ativo',"
            "'aguardando_cancelamento','inadimplente','bloqueado',"
            "'cancelado')",
            name="ck_aluno_b2c_estado_valido",
        ),
    )
    op.create_index("ix_alunos_b2c_telefone_e164", "alunos_b2c",
                    ["telefone_e164"], unique=True)
    op.create_index("ix_alunos_b2c_parceiro_id", "alunos_b2c",
                    ["parceiro_id"])

    op.create_table(
        "assinaturas_b2c",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aluno_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("alunos_b2c.id"), nullable=False),
        sa.Column("asaas_customer_id", sa.String(64), nullable=True),
        sa.Column("asaas_subscription_id", sa.String(64), nullable=True),
        sa.Column("status", sa.String(16), nullable=False,
                  server_default="pendente"),
        sa.Column("valor_centavos", sa.Integer(), nullable=False),
        sa.Column("ciclo", sa.String(16), nullable=False,
                  server_default="MONTHLY"),
        sa.Column("proximo_vencimento", sa.DateTime(timezone=True),
                  nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
        sa.CheckConstraint(
            "status IN ('pendente','ativa','atrasada','cancelada')",
            name="ck_assinatura_b2c_status_valido",
        ),
    )
    op.create_index("ix_assinaturas_b2c_aluno_id", "assinaturas_b2c",
                    ["aluno_id"])
    op.create_index("ix_assinaturas_b2c_asaas_subscription_id",
                    "assinaturas_b2c", ["asaas_subscription_id"])

    op.create_table(
        "envios_b2c",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aluno_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("alunos_b2c.id"), nullable=False),
        sa.Column("parceiro_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("parceiros_b2c.id"), nullable=False),
        sa.Column("imagem_url", sa.Text(), nullable=True),
        sa.Column("texto_ocr", sa.Text(), nullable=True),
        sa.Column("texto_final", sa.Text(), nullable=True),
        sa.Column("nota_total", sa.Integer(), nullable=True),
        sa.Column("notas_competencias",
                  postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("diagnostico", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True),
        sa.Column("gratis", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("tempo_processamento_ms", sa.Integer(), nullable=True),
        sa.Column("custo_estimado_centavos", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_envios_b2c_aluno_id", "envios_b2c", ["aluno_id"])
    op.create_index("ix_envios_b2c_parceiro_id", "envios_b2c",
                    ["parceiro_id"])
    op.create_index("ix_envios_b2c_created_at", "envios_b2c",
                    ["created_at"])

    op.create_table(
        "eventos_billing",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("aluno_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("alunos_b2c.id"), nullable=True),
        sa.Column("tipo", sa.String(64), nullable=False),
        sa.Column("dedupe_key", sa.String(128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()),
                  nullable=True),
        sa.Column("processado", sa.Boolean(), nullable=False,
                  server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_eventos_billing_aluno_id", "eventos_billing",
                    ["aluno_id"])
    op.create_index("ix_eventos_billing_dedupe_key", "eventos_billing",
                    ["dedupe_key"], unique=True)


def downgrade() -> None:
    op.drop_table("eventos_billing")
    op.drop_table("envios_b2c")
    op.drop_table("assinaturas_b2c")
    op.drop_table("alunos_b2c")
    op.drop_table("parceiros_b2c")
