#!/usr/bin/env python3
"""Testa o ciclo real de migrations contra um Postgres EFÊMERO.

`upgrade head → downgrade -1 → upgrade head`, com a cadeia inteira de
migrations, num Postgres descartável — sem docker, sem admin. Usado como
gate de §13.8 do runbook antes de aplicar migrations em produção.

Requer `pgserver` (bundla os binários do Postgres):
    pip install pgserver
Uso:
    python scripts/test_migration_cycle.py
Sai com 0 se o ciclo completo passou; !=0 se algum passo estourou.
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
PORTAL = BACKEND / "redato_backend" / "portal"
PY = sys.executable


def _alembic(args, db_url) -> int:
    env = {**os.environ, "DATABASE_URL": db_url, "PYTHONPATH": str(BACKEND)}
    print(f"\n$ alembic {' '.join(args)}")
    r = subprocess.run([PY, "-m", "alembic", "-c", "alembic.ini", *args],
                       cwd=str(PORTAL), env=env, capture_output=True, text=True)
    print(r.stdout[-2000:])
    if r.returncode != 0:
        print("STDERR:", r.stderr[-3000:])
    return r.returncode


def main() -> int:
    try:
        import pgserver
    except ImportError:
        print("ERRO: pip install pgserver (bundla o Postgres efêmero).")
        return 1

    pgdata = Path(tempfile.mkdtemp(prefix="pg_mig_"))
    print("Postgres efêmero em:", pgdata)
    srv = pgserver.get_server(pgdata)
    try:
        uri = srv.get_uri()
        passos = [
            ["upgrade", "head"], ["current"],
            ["downgrade", "-1"], ["current"],
            ["upgrade", "head"], ["current"],
        ]
        for args in passos:
            if _alembic(args, uri) != 0:
                print(f"\n❌ FALHOU em: alembic {' '.join(args)}")
                return 2
        print("\n✅ Ciclo completo OK: upgrade → downgrade -1 → upgrade.")
        return 0
    finally:
        srv.cleanup()
        print("Postgres efêmero limpo.")


if __name__ == "__main__":
    raise SystemExit(main())
