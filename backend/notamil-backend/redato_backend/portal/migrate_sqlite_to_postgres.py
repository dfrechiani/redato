#!/usr/bin/env python3
"""Migra dados legados do SQLite (Fase A) pro Postgres do portal (Fase B+).

Lê de `DATABASE_URL_SQLITE` e escreve em `DATABASE_URL` (Postgres). Schema
do Postgres deve estar criado antes (rodar `alembic upgrade head`).

Idempotente: se rodar 2×, não duplica. Detecta dados já migrados via
chave natural (foto_path + created_at + aluno_phone) e pula.

Dados migrados:
- `interactions` (tabela legada da Fase A) → tabela `interactions` no
  Postgres, com `aluno_turma_id=NULL`, `envio_id=NULL`, `source="whatsapp_v1"`.
- `alunos` (Fase A) e `turmas` (Fase A) NÃO são migradas — são entidades
  diferentes do modelo de portal. Coordenador precisa cadastrar
  escolas/turmas manualmente em M2 antes de re-vincular alunos.

Uso:
    DATABASE_URL_SQLITE=sqlite:///data/whatsapp/redato.db \\
    DATABASE_URL=postgresql://redato:redato@localhost:5433/redato_portal_dev \\
    python -m redato_backend.portal.migrate_sqlite_to_postgres
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from datetime import datetime, timezone

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session


def _parse_dt(value: Any) -> Optional[datetime]:
    """Converte ISO string (SQLite legado) → datetime tz-aware. Tolera
    None e datetime já parseado."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    s = str(value)
    try:
        # ISO 8601 — `2026-04-27T15:39:36.148192+00:00` ou similar
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

# Bootstrap pra rodar como script
_BACKEND = Path(__file__).resolve().parents[2]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

# Carrega .env se disponível
_env_path = _BACKEND / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip()
            if not os.environ.get(_k):
                os.environ[_k] = _v

from redato_backend.portal.models import Interaction  # noqa: E402


def _connect_sqlite(url: str):
    return create_engine(url, future=True)


def _connect_postgres(url: str):
    return create_engine(url, future=True)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    """Converte Row do SQLite (que tem _mapping) em dict."""
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return dict(row)


def _interaction_already_migrated(
    pg: Session, sqlite_row: Dict[str, Any],
) -> bool:
    """Heurística de idempotência: mesmo aluno_phone + missao_id +
    created_at já existe?"""
    created = _parse_dt(sqlite_row.get("created_at"))
    if created is None:
        return False
    stmt = select(Interaction).where(
        Interaction.aluno_phone == sqlite_row["aluno_phone"],
        Interaction.missao_id == sqlite_row["missao_id"],
        Interaction.created_at == created,
    )
    return pg.execute(stmt).first() is not None


def _migrate_interactions(sqlite_engine, pg_engine, *, dry_run: bool) -> Dict[str, int]:
    """Copia tabela interactions do SQLite pro Postgres."""
    with sqlite_engine.connect() as src_conn:
        rows = src_conn.execute(
            text("SELECT * FROM interactions ORDER BY id ASC")
        ).fetchall()

    n_total = len(rows)
    n_migrated = 0
    n_skipped = 0

    if dry_run:
        print(f"[dry-run] {n_total} linhas em interactions seriam migradas")
        return {"total": n_total, "migrated": 0, "skipped": n_total}

    with Session(pg_engine) as pg:
        for raw in rows:
            r = _row_to_dict(raw)
            if _interaction_already_migrated(pg, r):
                n_skipped += 1
                continue
            obj = Interaction(
                aluno_phone=r["aluno_phone"],
                aluno_turma_id=None,             # M4 popula
                envio_id=None,                    # M4 popula
                source="whatsapp_v1",
                turma_id=r.get("turma_id"),
                missao_id=r["missao_id"],
                activity_id=r["activity_id"],
                foto_path=r.get("foto_path"),
                foto_hash=r.get("foto_hash"),
                texto_transcrito=r.get("texto_transcrito"),
                ocr_quality_issues=r.get("ocr_quality_issues"),
                ocr_metrics=r.get("ocr_metrics"),
                redato_output=r.get("redato_output"),
                resposta_aluno=r.get("resposta_aluno"),
                elapsed_ms=r.get("elapsed_ms"),
                invalidated_at=_parse_dt(r.get("invalidated_at")),
                created_at=_parse_dt(r["created_at"]) or datetime.now(timezone.utc),
            )
            pg.add(obj)
            n_migrated += 1
            if n_migrated % 100 == 0:
                pg.flush()
        pg.commit()

    return {"total": n_total, "migrated": n_migrated, "skipped": n_skipped}


def _verify_count(sqlite_engine, pg_engine) -> Dict[str, int]:
    """Verifica que count(interactions) bate (excluindo skipped/já migrados)."""
    with sqlite_engine.connect() as src:
        sqlite_n = src.execute(text("SELECT COUNT(*) FROM interactions")).scalar()
    with pg_engine.connect() as pg:
        pg_n = pg.execute(
            text("SELECT COUNT(*) FROM interactions WHERE source = 'whatsapp_v1'")
        ).scalar()
    return {"sqlite_count": sqlite_n, "pg_v1_count": pg_n}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite-url", default=os.getenv("DATABASE_URL_SQLITE"),
                        help="ex.: sqlite:///data/whatsapp/redato.db")
    parser.add_argument("--postgres-url", default=os.getenv("DATABASE_URL"),
                        help="ex.: postgresql://user:pass@host:port/db")
    parser.add_argument("--dry-run", action="store_true",
                        help="Só conta, não escreve.")
    args = parser.parse_args()

    if not args.sqlite_url:
        # Fallback: arquivo padrão da Fase A
        default_db = _BACKEND / "data" / "whatsapp" / "redato.db"
        if default_db.exists():
            args.sqlite_url = f"sqlite:///{default_db}"
            print(f"sqlite-url default: {args.sqlite_url}")
        else:
            print("ERRO: --sqlite-url ou DATABASE_URL_SQLITE não configurada")
            sys.exit(1)
    if not args.postgres_url:
        print("ERRO: --postgres-url ou DATABASE_URL não configurada")
        sys.exit(1)

    print(f"SQLite source : {args.sqlite_url}")
    print(f"Postgres dest : {args.postgres_url}")
    print(f"Dry run       : {args.dry_run}")
    print()

    sqlite_engine = _connect_sqlite(args.sqlite_url)
    pg_engine = _connect_postgres(args.postgres_url)

    # Verifica que o Postgres tem schema (alembic foi rodado)
    with pg_engine.connect() as conn:
        try:
            conn.execute(text("SELECT 1 FROM interactions LIMIT 1"))
        except Exception as exc:
            print(f"ERRO: tabela interactions não existe no Postgres. "
                  f"Rode `alembic upgrade head` primeiro.\n  {exc}")
            sys.exit(1)

    stats = _migrate_interactions(sqlite_engine, pg_engine, dry_run=args.dry_run)
    print(f"interactions: total={stats['total']} migrated={stats['migrated']} "
          f"skipped={stats['skipped']}")

    if not args.dry_run:
        print()
        print("Verificando integridade...")
        counts = _verify_count(sqlite_engine, pg_engine)
        print(f"  SQLite count    : {counts['sqlite_count']}")
        print(f"  Postgres v1     : {counts['pg_v1_count']}")
        if counts["sqlite_count"] != counts["pg_v1_count"]:
            print(f"  ⚠️  divergência: {counts['sqlite_count'] - counts['pg_v1_count']} faltando")
        else:
            print("  ✓ count bate")


if __name__ == "__main__":
    main()
