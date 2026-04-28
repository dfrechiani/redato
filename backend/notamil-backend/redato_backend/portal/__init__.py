"""Portal do professor — Fase B+ (M1 onwards).

Camada de persistência SQLAlchemy + Postgres pro portal web.
Coexiste com a persistência legada do bot WhatsApp (SQLite via
[`redato_backend.whatsapp.persistence`](../whatsapp/persistence.py))
até M4 migrar o bot pra Postgres.

Convenções deste módulo:
- UUID v4 como PK em todas as tabelas novas (deixa interactions com
  INTEGER pra preservar compatibilidade com SQLite legado).
- Timestamps `created_at` / `updated_at` em todas as tabelas.
- Soft delete via `deleted_at` em entidades de produto (escolas,
  turmas, atividades). Coordenador, Professor e AlunoTurma usam
  flag `ativo` (mais simples; soft delete vem se necessário).
- ORM (não Core) em todas as queries.
"""
from redato_backend.portal.db import (
    Base, get_engine, get_session, get_sessionmaker,
)

__all__ = ["Base", "get_engine", "get_session", "get_sessionmaker"]
