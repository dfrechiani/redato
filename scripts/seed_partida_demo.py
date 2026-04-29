#!/usr/bin/env python3
"""Cria uma partida demo no banco pra Daniel testar via curl.

Útil pra exercitar GET /portal/partidas/{id}, PATCH e DELETE sem
precisar passar pelo POST + bot. Idempotente — re-rodar com mesmo
(atividade_id, grupo_codigo) atualiza prazo + alunos.

Pré-requisitos:
- Migration h0a1b2c3d4e5 aplicada
- Seed das 63 estruturais + ao menos 1 minideck (saude_mental por
  default) populado
- `--turma-id` e `--atividade-id` apontando pra entidades reais

Uso:
    python scripts/seed_partida_demo.py \
        --turma-id <uuid> --atividade-id <uuid>
        # dry-run mostra alunos da turma + plano

    python scripts/seed_partida_demo.py \
        --turma-id <uuid> --atividade-id <uuid> --apply
        # cria/atualiza
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend" / "notamil-backend"
sys.path.insert(0, str(BACKEND))

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass


logger = logging.getLogger("seed_partida_demo")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s %(message)s",
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--turma-id", required=True, type=uuid.UUID,
                         help="UUID da turma do Daniel")
    parser.add_argument("--atividade-id", required=True, type=uuid.UUID,
                         help="UUID da atividade dessa turma")
    parser.add_argument("--tema", default="saude_mental",
                         help="Slug do minideck (default: saude_mental)")
    parser.add_argument("--grupo-codigo", default="Grupo Demo",
                         help="Default: 'Grupo Demo'")
    parser.add_argument("--prazo-dias", type=int, default=7,
                         help="Dias a partir de hoje pro prazo (default 7)")
    parser.add_argument("--apply", action="store_true",
                         help="Sem isso, é dry-run")
    args = parser.parse_args()

    from sqlalchemy import select
    from sqlalchemy.exc import IntegrityError
    from sqlalchemy.orm import Session

    from redato_backend.portal.db import get_engine
    from redato_backend.portal.jogo_api import (
        _alunos_ids_da_partida, _set_alunos_partida,
    )
    from redato_backend.portal.models import (
        AlunoTurma, Atividade, JogoMinideck, PartidaJogo, Turma,
    )

    engine = get_engine()
    prazo_utc = (
        datetime.now(timezone.utc) + timedelta(days=args.prazo_dias)
    ).replace(microsecond=0)

    with Session(engine) as session:
        # Validações ---
        turma = session.get(Turma, args.turma_id)
        if turma is None:
            logger.error("turma_id %s não encontrada", args.turma_id)
            return 2
        ativ = session.get(Atividade, args.atividade_id)
        if ativ is None or ativ.deleted_at is not None:
            logger.error("atividade_id %s não encontrada", args.atividade_id)
            return 2
        if ativ.turma_id != turma.id:
            logger.error(
                "atividade %s pertence a turma %s, não %s",
                ativ.id, ativ.turma_id, turma.id,
            )
            return 2

        minideck = session.execute(
            select(JogoMinideck).where(
                JogoMinideck.tema == args.tema,
                JogoMinideck.ativo.is_(True),
            )
        ).scalar_one_or_none()
        if minideck is None:
            logger.error(
                "minideck %r não existe ou está inativo. Rode "
                "`scripts/seed_minideck.py %s --apply` antes.",
                args.tema, args.tema,
            )
            return 3

        alunos = session.execute(
            select(AlunoTurma).where(
                AlunoTurma.turma_id == turma.id,
                AlunoTurma.ativo.is_(True),
            ).order_by(AlunoTurma.nome.asc())
        ).scalars().all()
        if not alunos:
            logger.error("turma %s sem alunos ativos", turma.id)
            return 4

        # Default: pega os primeiros 4 alunos. Daniel pode customizar
        # a partir de aí — ainda é demo só pra criar 1 partida.
        alunos_grupo = alunos[:4]
        professor_id = ativ.criada_por_professor_id

        logger.info(
            "Plano: turma=%s atividade=%s tema=%s grupo=%r "
            "alunos=%d prazo=%s",
            turma.codigo, ativ.id, args.tema, args.grupo_codigo,
            len(alunos_grupo), prazo_utc.isoformat(),
        )
        for a in alunos_grupo:
            logger.info("  - %s (%s)", a.nome, a.id)

        existente = session.execute(
            select(PartidaJogo).where(
                PartidaJogo.atividade_id == ativ.id,
                PartidaJogo.grupo_codigo == args.grupo_codigo,
            )
        ).scalar_one_or_none()

        if existente is not None:
            logger.info(
                "Partida já existe — id=%s. Atualizaria alunos + "
                "prazo (idempotente).",
                existente.id,
            )
        else:
            logger.info("Partida nova seria criada.")

        if not args.apply:
            logger.info("DRY-RUN. Use --apply pra commitar.")
            return 0

        if existente is None:
            partida = PartidaJogo(
                atividade_id=ativ.id,
                minideck_id=minideck.id,
                grupo_codigo=args.grupo_codigo,
                cartas_escolhidas={},
                texto_montado="",
                prazo_reescrita=prazo_utc,
                criada_por_professor_id=professor_id,
            )
            _set_alunos_partida(partida, [a.id for a in alunos_grupo])
            session.add(partida)
            try:
                session.commit()
                session.refresh(partida)
                logger.info("✓ Partida criada: id=%s", partida.id)
            except IntegrityError as exc:
                session.rollback()
                logger.error("FALHA: %s", exc.orig)
                return 5
        else:
            existente.prazo_reescrita = prazo_utc
            _set_alunos_partida(existente, [a.id for a in alunos_grupo])
            session.commit()
            session.refresh(existente)
            logger.info(
                "✓ Partida atualizada: id=%s alunos=%d prazo=%s",
                existente.id, len(alunos_grupo),
                prazo_utc.isoformat(),
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
