"""Engine + sessionmaker SQLAlchemy pra Postgres do portal.

Padrão dual:
- Em produção e testes contra Postgres: lê `DATABASE_URL` do env.
- Em testes que querem isolamento: caller passa `database_url` direto.

Não cria tabelas automaticamente — Alembic é a fonte de verdade do
schema. Em smoke tests que rodam fora do Alembic, use `Base.metadata.
create_all(engine)` no setup.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """Base declarativa de todos os modelos do portal."""
    pass


_engine: Optional[Engine] = None
_SessionLocal: Optional[sessionmaker] = None


def _resolve_database_url(database_url: Optional[str] = None) -> str:
    if database_url:
        return database_url
    url = os.getenv("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL não configurada. Defina no .env ou passe "
            "explicitamente. Ver .env.example."
        )
    return url


def get_engine(database_url: Optional[str] = None,
               *, echo: bool = False) -> Engine:
    """Engine global. Reutiliza se já criada com a mesma URL."""
    global _engine
    url = _resolve_database_url(database_url)
    if _engine is not None and str(_engine.url) == url:
        return _engine
    _engine = create_engine(url, echo=echo, future=True, pool_pre_ping=True)
    return _engine


def get_sessionmaker(database_url: Optional[str] = None) -> sessionmaker:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(database_url), autoflush=False, autocommit=False,
        )
    return _SessionLocal


@contextmanager
def get_session(database_url: Optional[str] = None) -> Iterator[Session]:
    """Context manager pra sessão SQLAlchemy. Commit no exit normal,
    rollback em exceção, close sempre."""
    SessionLocal = get_sessionmaker(database_url)
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_for_tests() -> None:
    """Limpa engine/sessionmaker globais. Usar só em testes que trocam
    de DATABASE_URL no meio da execução."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
