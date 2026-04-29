#!/usr/bin/env python3
"""Reconciliar interactions órfãs em SQLite que ficaram fora de Postgres.

Bug original (M9.6, 2026-04-29 — ver migration g0a1b2c3d4e5):
quando aluno escolhia "2 — reavaliar como nova tentativa", o INSERT do
novo `Envio` falhava por causa do `uq_envio_atividade_aluno` (constraint
antiga sem `tentativa_n`). Como o INSERT do `Interaction` estava na
mesma transação SQLAlchemy, ambos rolavam back — só a 1ª tentativa
sobrevivia em Postgres. SQLite legado, em transação separada, salvava
todas as tentativas independentemente.

Resultado: dashboard do professor apontava pra interaction velha; nova
correção ficava órfã (gravada em SQLite mas invisível ao portal).

Este script identifica os órfãos em SQLite e os promove a `Interaction`
+ `Envio` em Postgres com o `tentativa_n` correto. Preserva
`created_at` original pra timeline ficar fidedigna.

Modos:

- `--dry-run` (default): só relata o que seria feito. Nenhum INSERT.
- `--apply`: executa os INSERTs. Logs vão pro arquivo
  `scripts/reconciliacao_<DATA>.log` na raiz do repo.

Idempotente: rodar `--apply` duas vezes resulta em 0 órfãos no segundo
run — o match SQLite ↔ Postgres usa `foto_hash`, que é estável.

Uso:
    cd <repo_root>
    python scripts/reconciliar_envios_orfaos.py             # dry-run
    python scripts/reconciliar_envios_orfaos.py --apply     # commit

Variáveis de ambiente:
    DATABASE_URL              Postgres (obrigatório)
    REDATO_WHATSAPP_DB        Path do SQLite (default
                              backend/notamil-backend/data/whatsapp/redato.db)
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sqlite3
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
BACKEND = REPO / "backend" / "notamil-backend"
sys.path.insert(0, str(BACKEND))

# Carrega .env do backend (DATABASE_URL etc.) antes de importar engine.
try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(BACKEND / ".env")
except ImportError:
    pass


logger = logging.getLogger("reconciliar_envios_orfaos")


# ──────────────────────────────────────────────────────────────────────
# Configuração
# ──────────────────────────────────────────────────────────────────────

def _today_log_path() -> Path:
    """Log path: scripts/reconciliacao_<YYYY-MM-DD>.log na raiz do repo.
    Data de hoje em UTC pra evitar duplicar quando script roda perto de
    meia-noite BRT."""
    hoje = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return REPO / "scripts" / f"reconciliacao_{hoje}.log"


def _setup_logging(apply: bool) -> Path:
    log_path = _today_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    fmt = "[%(asctime)s] %(levelname)s %(message)s"
    handlers: List[logging.Handler] = [logging.StreamHandler(sys.stdout)]
    # Em --apply abrimos o arquivo em append (idempotente). Em dry-run
    # só logamos no stdout pra não poluir o arquivo de evidências.
    if apply:
        handlers.append(logging.FileHandler(log_path, mode="a"))
    logging.basicConfig(level=logging.INFO, format=fmt, handlers=handlers)
    return log_path


def _sqlite_path() -> Path:
    override = os.getenv("REDATO_WHATSAPP_DB")
    if override:
        return Path(override)
    return BACKEND / "data" / "whatsapp" / "redato.db"


# ──────────────────────────────────────────────────────────────────────
# SQLite source
# ──────────────────────────────────────────────────────────────────────

def _ler_interactions_sqlite(sqlite_path: Path) -> List[Dict[str, Any]]:
    """Retorna interactions com correção concluída (`resposta_aluno`
    populada) e ainda não invalidadas (aluno não disse "ocr errado").
    Ignora rows sem foto_hash — sem ele não conseguimos cross-check
    contra Postgres com confiança."""
    if not sqlite_path.exists():
        logger.error("SQLite não encontrado em %s", sqlite_path)
        return []
    with sqlite3.connect(sqlite_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT * FROM interactions "
            "WHERE resposta_aluno IS NOT NULL "
            "AND foto_hash IS NOT NULL "
            "AND invalidated_at IS NULL "
            "ORDER BY created_at ASC"
        ).fetchall()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────────────────────────
# Postgres lookups
# ──────────────────────────────────────────────────────────────────────

def _parse_iso(s: str) -> datetime:
    """Tolera SQLite ISO sem tz (assume UTC) e ISO com `Z`."""
    s = s.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # Fallback bruto: SQLite às vezes salva sem tzinfo
        dt = datetime.strptime(s[:19], "%Y-%m-%dT%H:%M:%S")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _achar_aluno_turma(
    pg_session, aluno_phone: str, sqlite_turma_id: Optional[str],
) -> Optional[Tuple[uuid.UUID, uuid.UUID]]:
    """Resolve (aluno_turma_id, turma_id) por telefone. Se aluno está em
    múltiplas turmas ativas, prefere a do `sqlite_turma_id` quando bate.
    Retorna None se não achou ou ambíguo sem disambiguator."""
    from sqlalchemy import select
    from redato_backend.portal.models import AlunoTurma

    rows = pg_session.execute(
        select(AlunoTurma).where(
            AlunoTurma.telefone == aluno_phone,
            AlunoTurma.ativo.is_(True),
        )
    ).scalars().all()
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0].id, rows[0].turma_id
    # Múltiplas — usa turma_id do SQLite pra desambiguar (se ele veio
    # como UUID válido). Comparação string-vs-uuid via str().
    if sqlite_turma_id:
        for a in rows:
            if str(a.turma_id) == sqlite_turma_id:
                return a.id, a.turma_id
    logger.warning(
        "Aluno %s tem %d vínculos ativos sem disambiguator — pula",
        aluno_phone, len(rows),
    )
    return None


def _achar_atividade(
    pg_session, missao_codigo: str, turma_id: uuid.UUID,
    sqlite_created_at: datetime,
) -> Optional[uuid.UUID]:
    """Resolve atividade_id por (missao_codigo, turma_id, time window).
    Aceita atividade que estava ativa no momento do SQLite created_at,
    com tolerância de ±2 dias pras bordas (deploy lag, encerramento
    manual etc.). Se múltiplas, prefere a mais recente cuja janela
    inclui o timestamp."""
    from sqlalchemy import and_, select
    from redato_backend.portal.models import Atividade, Missao

    margem = timedelta(days=2)
    rows = pg_session.execute(
        select(Atividade)
        .join(Missao, Missao.id == Atividade.missao_id)
        .where(
            Missao.codigo == missao_codigo,
            Atividade.turma_id == turma_id,
            Atividade.deleted_at.is_(None),
            Atividade.data_inicio <= sqlite_created_at + margem,
            Atividade.data_fim >= sqlite_created_at - margem,
        )
        .order_by(Atividade.data_inicio.desc())
    ).scalars().all()
    if not rows:
        return None
    return rows[0].id


def _ja_existe_em_postgres(pg_session, foto_hash: str) -> bool:
    """True se Postgres já tem Interaction com esse foto_hash. Guarda
    contra duplicação no segundo `--apply`."""
    from sqlalchemy import select
    from redato_backend.portal.models import Interaction

    n = pg_session.execute(
        select(Interaction.id).where(Interaction.foto_hash == foto_hash)
    ).first()
    return n is not None


def _proxima_tentativa_n(
    pg_session, atividade_id: uuid.UUID, aluno_turma_id: uuid.UUID,
) -> int:
    from sqlalchemy import func, select
    from redato_backend.portal.models import Envio
    n = pg_session.execute(
        select(func.max(Envio.tentativa_n)).where(
            Envio.atividade_id == atividade_id,
            Envio.aluno_turma_id == aluno_turma_id,
        )
    ).scalar()
    return (n or 0) + 1


# ──────────────────────────────────────────────────────────────────────
# Execução
# ──────────────────────────────────────────────────────────────────────

def _inserir_orfan_postgres(
    pg_session, *, sqlite_row: Dict[str, Any],
    atividade_id: uuid.UUID, aluno_turma_id: uuid.UUID,
    tentativa_n: int,
) -> Tuple[int, uuid.UUID]:
    """Cria Interaction + Envio cross-linked. Preserva created_at e
    enviado_em do SQLite pra timeline ficar correta."""
    from redato_backend.portal.models import Envio, Interaction

    created_at = _parse_iso(sqlite_row["created_at"])

    interaction = Interaction(
        aluno_phone=sqlite_row["aluno_phone"],
        aluno_turma_id=aluno_turma_id,
        envio_id=None,
        source="whatsapp_portal",
        turma_id=sqlite_row.get("turma_id"),
        missao_id=sqlite_row["missao_id"],
        activity_id=sqlite_row["activity_id"],
        foto_path=sqlite_row.get("foto_path"),
        foto_hash=sqlite_row["foto_hash"],
        texto_transcrito=sqlite_row.get("texto_transcrito"),
        ocr_quality_issues=sqlite_row.get("ocr_quality_issues"),
        ocr_metrics=sqlite_row.get("ocr_metrics"),
        redato_output=sqlite_row.get("redato_output"),
        resposta_aluno=sqlite_row.get("resposta_aluno"),
        elapsed_ms=sqlite_row.get("elapsed_ms"),
        created_at=created_at,
    )
    pg_session.add(interaction)
    pg_session.flush()

    envio = Envio(
        atividade_id=atividade_id,
        aluno_turma_id=aluno_turma_id,
        interaction_id=interaction.id,
        enviado_em=created_at,
        tentativa_n=tentativa_n,
        created_at=created_at,
    )
    pg_session.add(envio)
    pg_session.flush()

    interaction.envio_id = envio.id
    return interaction.id, envio.id


def reconciliar(*, apply: bool) -> Dict[str, int]:
    """Roda a reconciliação. Retorna contadores pro caller logar resumo.

    Stats retornadas:
        - sqlite_total: rows lidas
        - already_in_pg: já existem em Postgres (skip)
        - sem_aluno: aluno_phone sem AlunoTurma ativo
        - sem_atividade: missao_id + janela sem Atividade
        - inseridos: novos Interaction+Envio criados (apply mode)
        - seriam_inseridos: candidatos válidos (dry-run mode)
    """
    from redato_backend.portal.db import get_engine
    from sqlalchemy.orm import Session

    sqlite_path = _sqlite_path()
    rows = _ler_interactions_sqlite(sqlite_path)
    logger.info(
        "Lidas %d interactions do SQLite (com resposta_aluno + foto_hash) "
        "de %s", len(rows), sqlite_path,
    )

    stats = {
        "sqlite_total": len(rows),
        "already_in_pg": 0,
        "sem_aluno": 0,
        "sem_atividade": 0,
        "inseridos": 0,
        "seriam_inseridos": 0,
    }

    if not rows:
        return stats

    engine = get_engine()
    with Session(engine) as session:
        for row in rows:
            foto_hash = row["foto_hash"]
            if _ja_existe_em_postgres(session, foto_hash):
                stats["already_in_pg"] += 1
                continue

            sqlite_created_at = _parse_iso(row["created_at"])

            aluno_match = _achar_aluno_turma(
                session, row["aluno_phone"], row.get("turma_id"),
            )
            if aluno_match is None:
                stats["sem_aluno"] += 1
                logger.warning(
                    "Orphan SEM ALUNO: phone=%s sqlite_id=%s "
                    "missao=%s — pula",
                    row["aluno_phone"], row["id"], row["missao_id"],
                )
                continue
            aluno_turma_id, turma_id = aluno_match

            atividade_id = _achar_atividade(
                session, row["missao_id"], turma_id, sqlite_created_at,
            )
            if atividade_id is None:
                stats["sem_atividade"] += 1
                logger.warning(
                    "Orphan SEM ATIVIDADE: phone=%s missao=%s "
                    "turma=%s ts=%s — pula",
                    row["aluno_phone"], row["missao_id"], turma_id,
                    sqlite_created_at.isoformat(),
                )
                continue

            tentativa_n = _proxima_tentativa_n(
                session, atividade_id, aluno_turma_id,
            )

            if apply:
                inter_id, envio_id = _inserir_orfan_postgres(
                    session, sqlite_row=row,
                    atividade_id=atividade_id,
                    aluno_turma_id=aluno_turma_id,
                    tentativa_n=tentativa_n,
                )
                logger.info(
                    "INSERIU phone=%s missao=%s tentativa_n=%d "
                    "interaction_id=%d envio_id=%s ts=%s",
                    row["aluno_phone"], row["missao_id"], tentativa_n,
                    inter_id, envio_id, sqlite_created_at.isoformat(),
                )
                stats["inseridos"] += 1
            else:
                logger.info(
                    "SERIA INSERIDO phone=%s missao=%s tentativa_n=%d "
                    "atividade=%s aluno_turma=%s ts=%s "
                    "(foto_hash=%s sqlite_id=%s)",
                    row["aluno_phone"], row["missao_id"], tentativa_n,
                    atividade_id, aluno_turma_id,
                    sqlite_created_at.isoformat(),
                    foto_hash[:8], row["id"],
                )
                stats["seriam_inseridos"] += 1

        if apply:
            session.commit()
        else:
            session.rollback()

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--apply", action="store_true",
        help=("Executa os INSERTs em Postgres. SEM --apply, é dry-run "
              "(default)."),
    )
    args = parser.parse_args()

    log_path = _setup_logging(args.apply)
    logger.info("=" * 60)
    logger.info(
        "Início — modo=%s log=%s",
        "APPLY" if args.apply else "DRY-RUN", log_path,
    )

    try:
        stats = reconciliar(apply=args.apply)
    except Exception:
        logger.exception("FALHA inesperada — abortando")
        return 2

    logger.info("Fim — stats: %s", json.dumps(stats, ensure_ascii=False))
    if not args.apply and stats.get("seriam_inseridos", 0) > 0:
        logger.info(
            "DRY-RUN concluído. Use --apply pra commitar em Postgres."
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
