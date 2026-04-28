"""Cleanup periódico de tokens expirados (M3).

3 funções idempotentes:
- `cleanup_primeiro_acesso_expirados()`: NULA tokens de primeiro
  acesso vencidos (NÃO deleta o usuário — só limpa colunas de token).
- `cleanup_reset_tokens_expirados()`: idem pra reset de senha.
- `cleanup_blocklist_expirada()`: DELETE em token_blocklist quando
  exp_original < now (após exp natural não há razão pra manter).

CLI: `python -m redato_backend.portal.auth.cleanup`

Em produção: cron daily.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from sqlalchemy import update, delete
from sqlalchemy.orm import Session


def cleanup_primeiro_acesso_expirados(session: Session) -> int:
    """Limpa tokens de primeiro acesso expirados em coordenadores e
    professores. Retorna total de linhas afetadas."""
    from redato_backend.portal.models import Coordenador, Professor
    agora = datetime.now(timezone.utc)
    affected = 0
    for Model in (Coordenador, Professor):
        result = session.execute(
            update(Model)
            .where(
                Model.primeiro_acesso_token.is_not(None),
                Model.primeiro_acesso_expira_em < agora,
            )
            .values(primeiro_acesso_token=None,
                    primeiro_acesso_expira_em=None)
        )
        affected += result.rowcount or 0
    return affected


def cleanup_reset_tokens_expirados(session: Session) -> int:
    """Limpa tokens de reset de senha expirados."""
    from redato_backend.portal.models import Coordenador, Professor
    agora = datetime.now(timezone.utc)
    affected = 0
    for Model in (Coordenador, Professor):
        result = session.execute(
            update(Model)
            .where(
                Model.reset_password_token.is_not(None),
                Model.reset_password_expira_em < agora,
            )
            .values(reset_password_token=None,
                    reset_password_expira_em=None)
        )
        affected += result.rowcount or 0
    return affected


def cleanup_blocklist_expirada(session: Session) -> int:
    """DELETE entradas da blocklist com exp_original passada."""
    from redato_backend.portal.models import TokenBlocklist
    agora = datetime.now(timezone.utc)
    result = session.execute(
        delete(TokenBlocklist).where(TokenBlocklist.exp_original < agora)
    )
    return result.rowcount or 0


def run_all(session: Session) -> Dict[str, int]:
    """Roda os 3 cleanups, comita ao final."""
    stats = {
        "primeiro_acesso_expirados": cleanup_primeiro_acesso_expirados(session),
        "reset_tokens_expirados": cleanup_reset_tokens_expirados(session),
        "blocklist_removida": cleanup_blocklist_expirada(session),
    }
    session.commit()
    return stats


def main():
    """CLI entry-point."""
    backend = Path(__file__).resolve().parents[3]
    env_path = backend / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if not os.environ.get(k):
                    os.environ[k] = v

    if str(backend) not in sys.path:
        sys.path.insert(0, str(backend))

    from redato_backend.portal.db import get_engine

    engine = get_engine()
    with Session(engine) as session:
        stats = run_all(session)

    print(f"[{datetime.now(timezone.utc).isoformat()}] cleanup auth:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
