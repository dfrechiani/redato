"""Alembic env — sync mode (psycopg2).

Lê DATABASE_URL do ambiente em vez do alembic.ini. Permite usar a
mesma URL que o app usa, sem duplicar config.

Carrega `.env` automaticamente via python-dotenv se disponível, pra
DX local (rodar `alembic upgrade head` sem precisar exportar var).
"""
from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# ──────────────────────────────────────────────────────────────────────
# Bootstrap: garante que `redato_backend` está importável + carrega .env
# ──────────────────────────────────────────────────────────────────────
_PORTAL_DIR = Path(__file__).resolve().parent.parent
_BACKEND_DIR = _PORTAL_DIR.parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

# Carrega .env do backend se existir.
_env_path = _BACKEND_DIR / ".env"
if _env_path.exists():
    for _line in _env_path.read_text().splitlines():
        if "=" in _line and not _line.strip().startswith("#"):
            _k, _v = _line.split("=", 1)
            _k, _v = _k.strip(), _v.strip()
            if not os.environ.get(_k):
                os.environ[_k] = _v

# Importa modelos pra Base.metadata ficar populada (autogenerate).
from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402

target_metadata = Base.metadata


# ──────────────────────────────────────────────────────────────────────
# Alembic config
# ──────────────────────────────────────────────────────────────────────
config = context.config

# Override sqlalchemy.url do .ini com DATABASE_URL do env.
_db_url = os.getenv("DATABASE_URL")
if not _db_url:
    raise RuntimeError(
        "DATABASE_URL não configurada. Defina no .env ou exporte. "
        "Ex.: postgresql://redato:redato@localhost:5433/redato_portal_dev"
    )
config.set_main_option("sqlalchemy.url", _db_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)


def run_migrations_offline() -> None:
    """Modo offline: emite SQL sem conectar."""
    context.configure(
        url=_db_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Modo online: conecta e aplica."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
