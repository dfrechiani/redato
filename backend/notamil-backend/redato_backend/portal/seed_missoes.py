#!/usr/bin/env python3
"""Seed das 5 missões REJ 1S (M4).

Idempotente: rodar múltiplas vezes não duplica. Faz UPSERT por
`codigo` (chave natural).

Uso:
    python -m redato_backend.portal.seed_missoes [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List

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


def seed_missoes(session: Session, *, dry_run: bool = False) -> Dict[str, int]:
    """Idempotente. Retorna {novas, atualizadas, inalteradas}."""
    novas = 0
    atualizadas = 0
    inalteradas = 0
    for spec in MISSOES_REJ_1S:
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
    args = parser.parse_args()

    if not os.getenv("DATABASE_URL"):
        print("ERRO: DATABASE_URL não configurada.")
        sys.exit(1)

    engine = get_engine()
    with Session(engine) as session:
        stats = seed_missoes(session, dry_run=args.dry_run)

    print(f"seed_missoes ({'dry-run' if args.dry_run else 'commit'}):")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    print(f"  total catálogo: {len(MISSOES_REJ_1S)}")


if __name__ == "__main__":
    main()
