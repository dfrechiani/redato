#!/usr/bin/env python3
"""Seed das missões REJ — 1S (5) + 2S (7).

Idempotente: rodar múltiplas vezes não duplica. Faz UPSERT por
`codigo` (chave natural).

Sobre o prefixo "RJ":
- Vem de "Redação em Jogo", nome técnico legado.
- App agora chama "Projeto ATO", livros impressos usam "ATO2·OFxx·MF",
  mas no banco e em prompts/detectores o prefixo "RJ" continua.
- Migração coordenada de RJ → ATO (DB + bot regex + prompts + livros)
  é trabalho separado, fora desta entrega.

Uso:
    python -m redato_backend.portal.seed_missoes [--dry-run]
    python -m redato_backend.portal.seed_missoes --serie 2S [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

# Bootstrap pra rodar como script
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Carrega .env
_env_path = _BACKEND / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip()
            if not os.environ.get(_k):
                os.environ[_k] = _v

from redato_backend.portal.db import get_engine  # noqa: E402
from redato_backend.portal.models import Missao  # noqa: E402


# Catálogo canônico — fonte de verdade. Spec:
# docs/redato/v3/redato_1S_criterios.md
# Títulos: nomes oficiais das oficinas pedagógicas da 1ª série (em
# `series_oficinas_canonico.md`). Modo de correção continua sendo o
# que o Redato avalia em cada uma.
MISSOES_REJ_1S: List[Dict[str, object]] = [
    {
        "codigo": "RJ1·OF10·MF", "serie": "1S", "oficina_numero": 10,
        "titulo": "Jogo Dissertativo", "modo_correcao": "foco_c3",
    },
    {
        "codigo": "RJ1·OF11·MF", "serie": "1S", "oficina_numero": 11,
        "titulo": "Conectivos Argumentativos", "modo_correcao": "foco_c4",
    },
    {
        "codigo": "RJ1·OF12·MF", "serie": "1S", "oficina_numero": 12,
        "titulo": "Leilão de Soluções", "modo_correcao": "foco_c5",
    },
    {
        "codigo": "RJ1·OF13·MF", "serie": "1S", "oficina_numero": 13,
        "titulo": "Construindo Argumentos", "modo_correcao": "completo_parcial",
    },
    {
        "codigo": "RJ1·OF14·MF", "serie": "1S", "oficina_numero": 14,
        "titulo": "Jogo de Redação", "modo_correcao": "completo",
    },
]

# Catálogo 2S — 7 oficinas com Missão Final corrigida pelo Redato.
# Spec: livro LIVRO_ATO_2S_PROF.html + decisões registradas:
#   • OF01 Diagnóstico → completo_parcial (recebe nota geral sem
#     aplicar rigor da rubrica completa). Decisão pedagógica do Daniel.
#   • OF06 cobre C2 + C3 mas não há modo `foco_c2_c3` — usamos
#     `foco_c2`. Idem OF09 (cobre C3+C4) → `foco_c3`.
MISSOES_REJ_2S: List[Dict[str, object]] = [
    {
        "codigo": "RJ2·OF01·MF", "serie": "2S", "oficina_numero": 1,
        "titulo": "Diagnóstico", "modo_correcao": "completo_parcial",
    },
    {
        "codigo": "RJ2·OF04·MF", "serie": "2S", "oficina_numero": 4,
        "titulo": "Fontes e Citações", "modo_correcao": "foco_c2",
    },
    {
        "codigo": "RJ2·OF06·MF", "serie": "2S", "oficina_numero": 6,
        "titulo": "Da Notícia ao Artigo", "modo_correcao": "foco_c2",
    },
    {
        "codigo": "RJ2·OF07·MF", "serie": "2S", "oficina_numero": 7,
        "titulo": "Tese e Argumentos", "modo_correcao": "foco_c3",
    },
    {
        "codigo": "RJ2·OF09·MF", "serie": "2S", "oficina_numero": 9,
        "titulo": "Expedição Argumentativa", "modo_correcao": "foco_c3",
    },
    {
        "codigo": "RJ2·OF12·MF", "serie": "2S", "oficina_numero": 12,
        "titulo": "Leilão de Soluções", "modo_correcao": "foco_c5",
    },
    {
        "codigo": "RJ2·OF13·MF", "serie": "2S", "oficina_numero": 13,
        "titulo": "Jogo de Redação Completo", "modo_correcao": "completo",
    },
]

# Catálogo agregado — fonte de verdade pro seed e pra migrations.
MISSOES_TODAS: List[Dict[str, object]] = MISSOES_REJ_1S + MISSOES_REJ_2S


def seed_missoes(
    session: Session, *,
    dry_run: bool = False,
    serie: Optional[str] = None,
) -> Dict[str, int]:
    """Idempotente. Retorna {novas, atualizadas, inalteradas}.

    `serie` opcional filtra catálogo: '1S', '2S', '3S'. None = tudo.
    """
    catalogo = MISSOES_TODAS
    if serie:
        catalogo = [m for m in MISSOES_TODAS if m["serie"] == serie]

    novas = 0
    atualizadas = 0
    inalteradas = 0
    for spec in catalogo:
        existing = session.execute(
            select(Missao).where(Missao.codigo == spec["codigo"])
        ).scalar_one_or_none()
        if existing is None:
            if not dry_run:
                session.add(Missao(**spec, ativa=True))
            novas += 1
        else:
            changed = False
            for k, v in spec.items():
                if getattr(existing, k) != v:
                    if not dry_run:
                        setattr(existing, k, v)
                    changed = True
            if changed:
                atualizadas += 1
            else:
                inalteradas += 1
    if not dry_run:
        session.commit()
    return {"novas": novas, "atualizadas": atualizadas,
            "inalteradas": inalteradas}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Reporta sem persistir.")
    parser.add_argument("--serie", choices=["1S", "2S", "3S"], default=None,
                        help="Filtra catálogo por série. Default: tudo.")
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        print("ERRO: DATABASE_URL não configurada.")
        sys.exit(1)

    engine = get_engine()
    with Session(engine) as session:
        stats = seed_missoes(session, dry_run=args.dry_run, serie=args.serie)

    catalogo_size = len([
        m for m in MISSOES_TODAS
        if not args.serie or m["serie"] == args.serie
    ])
    label = args.serie or "todas"
    print(f"seed_missoes [{label}] ({'dry-run' if args.dry_run else 'commit'}):")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  total catálogo: {catalogo_size}")


if __name__ == "__main__":
    main()
