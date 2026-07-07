#!/usr/bin/env python3
"""Seed de um parceiro B2C (SPEC_B2C_REDATO.md §4 F9, §10.4).

Cria (idempotente) um parceiro pra piloto/dev. Enquanto os 3 parceiros
reais não fecham contrato, usa o fake "DEMO". Não valida walletId contra
a API Asaas aqui (isso é o endpoint POST /admin/b2c/parceiros) — este
script é o atalho de dev/seed.

Uso:
    DATABASE_URL=postgres://... python scripts/seed_parceiro.py \
        --slug demo --codigo DEMO --nome-publico "Correção DEMO" \
        --nome-professor "Prof. Demo" --preco-centavos 3990

Sem argumentos, cria o parceiro DEMO padrão.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed de parceiro B2C")
    parser.add_argument("--slug", default="demo")
    parser.add_argument("--codigo", default="DEMO")
    parser.add_argument("--nome-publico", default="Correção DEMO")
    parser.add_argument("--nome-professor", default="Prof. Demo")
    parser.add_argument("--wallet-id", default=None)
    parser.add_argument("--share-pct", type=float, default=None)
    parser.add_argument("--preco-centavos", type=int, default=3990)
    args = parser.parse_args()

    from sqlalchemy import select
    from redato_backend.portal.db import get_session
    from redato_backend.portal.models import ParceiroB2C

    with get_session() as s:
        existente = s.execute(
            select(ParceiroB2C).where(ParceiroB2C.slug == args.slug)
        ).scalar_one_or_none()
        if existente is not None:
            print(f"Parceiro '{args.slug}' já existe (id={existente.id}). Nada a fazer.")
            return 0
        p = ParceiroB2C(
            slug=args.slug,
            codigo_entrada=args.codigo.upper(),
            nome_publico=args.nome_publico,
            nome_professor=args.nome_professor,
            wallet_id_asaas=args.wallet_id,
            share_pct=args.share_pct,
            preco_centavos=args.preco_centavos,
            branding={
                "saudacao": f"Fala! Aqui é a {args.nome_publico} 👋",
                "emoji": "✍️",
                "assinatura": args.nome_publico,
                "cor": "#0A2540",
            },
            ativo=True,
        )
        s.add(p)
        s.flush()
        pid = str(p.id)

    print(f"Parceiro '{args.slug}' criado (id={pid}).")
    print(f"Deep link: wa.me/<B2C_NUMERO_WHATSAPP>?text=QUERO+{args.codigo.upper()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
