"""envios diagnostico (Fase 2 — diagnóstico cognitivo)

Adiciona coluna `envios.diagnostico` (JSONB nullable) pra persistir
diagnóstico cognitivo gerado pelo pipeline GPT-4.1 a partir de
`redato_output` + texto da redação.

Fase 1 (commit 010686c) entregou os 40 descritores observáveis em
`docs/redato/v3/diagnostico/descritores.yaml`.

Fase 2 (esta migration + módulo `redato_backend/diagnostico/`) gera,
pra cada envio com correção bem-sucedida, um JSON estruturado:

    {
      "schema_version": "1.0",
      "modelo_usado": "gpt-4.1-2025-04-14",
      "gerado_em": "2026-05-03T12:34:56Z",
      "latencia_ms": 8421,
      "custo_estimado_usd": 0.041,
      "descritores": [
        {
          "id": "C3.001",
          "status": "lacuna" | "dominio" | "incerto",
          "evidencias": ["trecho 1", "trecho 2"],  # max 3
          "confianca": "alta" | "media" | "baixa"
        },
        ... 40 entries
      ],
      "lacunas_prioritarias": ["C3.001", "C5.003", ...],  # top 5
      "resumo_qualitativo": "Aluno demonstra ...",
      "recomendacao_breve": "Reforço prioritário em ..."
    }

Por que JSONB (não tabela relacional separada):

- Schema do diagnóstico evolui (descritores podem ser adicionados,
  campos auxiliares podem mudar). JSONB acomoda isso sem migration
  por mudança.
- Diagnóstico é unidade lógica do envio — não tem queries que
  beneficiam de normalização (não vamos buscar "todos os envios
  que violam C3.001" via SQL; isso vai por agregação na Fase 3).
- Postgres JSONB tem GIN index se for necessário no futuro
  (ex.: `WHERE diagnostico @> '{"descritores":[{"id":"C3.001"}]}'`).
- Mesma estratégia de `interactions.redato_output` — código
  existente já trata JSON serializado pelos helpers `_parse_*`.

Por que nullable:

- Diagnóstico é opcional — se o pipeline GPT-4.1 falhar ou estiver
  desabilitado (`REDATO_DIAGNOSTICO_HABILITADO=false`), envio é
  persistido sem diagnóstico e UX do aluno não muda.
- Envios pré-Fase 2 ficam com NULL. Endpoint de retry
  (`POST /portal/envios/{id}/diagnosticar`) preenche sob demanda.

Revision ID: k0a1b2c3d4e5
Revises: j0a1b2c3d4e5
Create Date: 2026-05-03 09:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'k0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'j0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """ADD COLUMN envios.diagnostico JSONB NULL."""
    op.add_column(
        "envios",
        sa.Column(
            "diagnostico",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    """DROP COLUMN envios.diagnostico — perda de dado intencional.

    Diagnósticos persistidos serão apagados. Em prod, o operador
    deve fazer dump de `envios.diagnostico` antes de rodar downgrade
    se quiser preservar (não é entregue ao aluno, mas pode ser útil
    pra análise pedagógica retroativa).
    """
    op.drop_column("envios", "diagnostico")
