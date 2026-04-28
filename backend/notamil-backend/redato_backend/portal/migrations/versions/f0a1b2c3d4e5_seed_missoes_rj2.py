"""seed missoes RJ2 (2S)

Insere as 7 missões da 2ª série no catálogo `missoes`. Idempotente via
INSERT ... ON CONFLICT (codigo) DO NOTHING — segurança extra pra
ambientes onde alguém possa ter rodado `seed_missoes.py --serie 2S`
antes desta migration.

Catálogo (mantido em sincronia com
`redato_backend.portal.seed_missoes.MISSOES_REJ_2S` — fonte de verdade):

  RJ2·OF01·MF — Diagnóstico             — completo_parcial
  RJ2·OF04·MF — Fontes e Citações       — foco_c2
  RJ2·OF06·MF — Da Notícia ao Artigo    — foco_c2
  RJ2·OF07·MF — Tese e Argumentos       — foco_c3
  RJ2·OF09·MF — Expedição Argumentativa — foco_c3
  RJ2·OF12·MF — Leilão de Soluções      — foco_c5
  RJ2·OF13·MF — Jogo de Redação Completo— completo

Decisões pedagógicas registradas:
- OF01 Diagnóstico → completo_parcial (recebe nota geral sem aplicar
  rigor da rubrica completa). Decisão do Daniel.
- OF06 cobre C2+C3 e OF09 cobre C3+C4, mas o schema só permite foco
  unidimensional. Pegamos o foco principal de cada uma (C2 e C3 resp).
- Modos foco_c1/c2 já habilitados pela migration e9f1c8a2b4d5.

Sobre o prefixo "RJ":
- Vem de "Redação em Jogo", nome técnico legado.
- App agora chama "Projeto ATO", livros impressos usam "ATO2·OFxx·MF",
  mas no banco e em prompts/detectores o prefixo "RJ" continua.
  Migração coordenada RJ → ATO é trabalho separado.

Em produção, a 1S (5 missões) já foi seedada via M4. Esta migration
acrescenta apenas as 7 da 2S; não toca nas existentes.

Revision ID: f0a1b2c3d4e5
Revises: e9f1c8a2b4d5
Create Date: 2026-04-27 14:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'f0a1b2c3d4e5'
down_revision: Union[str, Sequence[str], None] = 'e9f1c8a2b4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Catálogo 2S — duplicado aqui pra migration ser auto-contida (não
# importa do código da app, que pode mudar). Se atualizar, manter em
# sincronia com seed_missoes.MISSOES_REJ_2S.
_MISSOES_2S = [
    ("RJ2·OF01·MF", "2S",  1, "Diagnóstico",              "completo_parcial"),
    ("RJ2·OF04·MF", "2S",  4, "Fontes e Citações",        "foco_c2"),
    ("RJ2·OF06·MF", "2S",  6, "Da Notícia ao Artigo",     "foco_c2"),
    ("RJ2·OF07·MF", "2S",  7, "Tese e Argumentos",        "foco_c3"),
    ("RJ2·OF09·MF", "2S",  9, "Expedição Argumentativa",  "foco_c3"),
    ("RJ2·OF12·MF", "2S", 12, "Leilão de Soluções",       "foco_c5"),
    ("RJ2·OF13·MF", "2S", 13, "Jogo de Redação Completo", "completo"),
]


def upgrade() -> None:
    """INSERT idempotente. ON CONFLICT (codigo) DO NOTHING garante que
    rodar 2× não duplica e que coexistir com seed_missoes.py é seguro."""
    for codigo, serie, oficina, titulo, modo in _MISSOES_2S:
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
    """Remove só as 7 da 2S — não toca nas 1S nem em qualquer outra
    missão criada manualmente."""
    codigos = ", ".join(f"'{c}'" for c, *_ in _MISSOES_2S)
    op.execute(f"DELETE FROM missoes WHERE codigo IN ({codigos})")
