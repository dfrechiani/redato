"""seed missoes RJ3 (3S)

Insere 11 das 15 missões da 3ª série no catálogo `missoes`. Idempotente
via INSERT ... ON CONFLICT (codigo) DO NOTHING — segura pra coexistir
com seed_missoes.py manual ou re-runs.

Catálogo 3S (11 das 15 oficinas do livro LIVRO_ATO_3S_v8_PROF.html):

  RJ3·OF01·MF — Redato — seu corretor de bolso  — completo_parcial
  RJ3·OF03·MF — Dossiê: Repertório + Análise   — foco_c2
  RJ3·OF04·MF — Dossiê: Tema + Problemática    — foco_c2
  RJ3·OF05·MF — Dossiê: Agentes + Proposta     — foco_c5
  RJ3·OF06·MF — Dossiê: Proposta Completa      — foco_c5
  RJ3·OF07·MF — Jogo do Corretor               — completo_parcial
  RJ3·OF09·MF — Simulado 1                     — completo
  RJ3·OF10·MF — Revisão Cooperativa            — completo_parcial
  RJ3·OF11·MF — Simulado 2 + IA                — completo
  RJ3·OF14·MF — Simulado Final 1               — completo
  RJ3·OF15·MF — Simulado Final 2 + Fechamento  — completo

Excluídas intencionalmente (registradas em
docs/redato/v3/oficinas_3s_status.md):

- OF02 Conectivos + Coesão — só fluxo de chat, sem produção avaliável
  pelo Redato.
- OF08 Análise de Erros Comuns — pediria foco_c1, mas esse modo está
  ADIADO em código (decisão Daniel 2026-04-28). Habilitar exige enum
  FOCO_C1 + tool schema + scoring branch + DEFAULT_MODEL. Sessão
  dedicada futura — não bloqueia adoção das 11 outras 3S agora.
- OF12, OF13 Jogos de Redação Completo — dependem de sistema de cartas
  3S (slots A/AÇ/ME/F com cartas argumentativas E01-E64) que é
  diferente do sistema 1S (cartas com classes gramaticais). Sessão
  dedicada futura.

Decisão sobre `modo_correcao = 'completo'`:
- CHECK constraint da tabela aceita apenas valores em
  MODO_CORRECAO_VALIDOS (foco_c1..c5, completo_parcial, completo).
  No router (`missions/router.py:_MISSAO_TO_MODE`), o enum equivalente
  é `MissionMode.COMPLETO_INTEGRAL` — nome do enum em Python, valor
  canônico no banco continua "completo".
- Simulado 1, 2, Final 1, Final 2 vão por OF14-equivalent (Sonnet
  4.6 v2 ou GPT-FT BTBOS5VF dependendo do REDATO_OF14_BACKEND).

Sobre o prefixo "RJ":
- Vem de "Redação em Jogo", nome legado. App agora chama "Projeto
  ATO" mas DB e prompts mantêm "RJ" pra evitar refactor coordenado.

Revision ID: j0a1b2c3d4e5
Revises: i0a1b2c3d4e5
Create Date: 2026-05-02 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'j0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'i0a1b2c3d4e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Catálogo 3S — duplicado aqui pra migration ser auto-contida.
# Se atualizar, manter em sincronia com seed_missoes.MISSOES_REJ_3S
# (quando criado).
_MISSOES_3S = [
    ("RJ3·OF01·MF", "3S",  1, "Redato — seu corretor de bolso",  "completo_parcial"),
    ("RJ3·OF03·MF", "3S",  3, "Dossiê: Repertório + Análise",    "foco_c2"),
    ("RJ3·OF04·MF", "3S",  4, "Dossiê: Tema + Problemática",     "foco_c2"),
    ("RJ3·OF05·MF", "3S",  5, "Dossiê: Agentes + Proposta",      "foco_c5"),
    ("RJ3·OF06·MF", "3S",  6, "Dossiê: Proposta Completa",       "foco_c5"),
    ("RJ3·OF07·MF", "3S",  7, "Jogo do Corretor",                "completo_parcial"),
    ("RJ3·OF09·MF", "3S",  9, "Simulado 1",                      "completo"),
    ("RJ3·OF10·MF", "3S", 10, "Revisão Cooperativa",             "completo_parcial"),
    ("RJ3·OF11·MF", "3S", 11, "Simulado 2 + IA",                 "completo"),
    ("RJ3·OF14·MF", "3S", 14, "Simulado Final 1",                "completo"),
    ("RJ3·OF15·MF", "3S", 15, "Simulado Final 2 + Fechamento",   "completo"),
]


def upgrade() -> None:
    """INSERT idempotente. ON CONFLICT (codigo) DO NOTHING garante que
    rodar 2× não duplica e coexiste com seed_missoes manual."""
    for codigo, serie, oficina, titulo, modo in _MISSOES_3S:
        op.execute(
            f"""
            INSERT INTO missoes (
                id, codigo, serie, oficina_numero, titulo,
                modo_correcao, ativa, created_at, updated_at
            ) VALUES (
                gen_random_uuid(), '{codigo}', '{serie}', {oficina},
                '{titulo.replace("'", "''")}', '{modo}', TRUE,
                NOW() AT TIME ZONE 'UTC', NOW() AT TIME ZONE 'UTC'
            )
            ON CONFLICT (codigo) DO NOTHING
            """
        )


def downgrade() -> None:
    """Remove só as 12 da 3S — não toca em 1S, 2S, ou outras criadas
    manualmente. Falha se houver atividades vinculadas (FK em
    atividades.missao_id) — limpe atividades primeiro se realmente
    precisar reverter (perda de dado pedagógico real)."""
    codigos = ", ".join(f"'{c}'" for c, *_ in _MISSOES_3S)
    op.execute(f"DELETE FROM missoes WHERE codigo IN ({codigos})")
