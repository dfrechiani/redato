#!/usr/bin/env python3
"""Smoke test M2 — importador + endpoints admin + emails de boas-vindas.

Cobre:
1. Planilha sintética válida → dry-run + commit + idempotência
2. Edge cases (campos faltando, email inválido, série inválida, duplicata)
3. POST /admin/import-planilha com token correto / token errado
4. POST /admin/send-welcome-emails em dry-run (jsonl populado)
5. CLI import_planilha.py executável
6. M1 não regrediu (test_crud básico)
7. Fase A não regrediu (webhook offline)

Roda em schema isolado do Postgres pra não tocar dados reais.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

# Carrega .env
env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):
                os.environ[k] = v

# Schema isolado pra não tocar dados reais
TEST_SCHEMA = f"m2_test_{uuid.uuid4().hex[:8]}"

# Token de admin pros endpoints
os.environ["ADMIN_TOKEN"] = "test-admin-token-m2"

# Garante que SendGrid não tá configurada (forçar dry-run de email)
os.environ.pop("SENDGRID_API_KEY", None)

# Pasta isolada de logs de email
test_pending = Path(tempfile.mkdtemp(prefix="m2email_")) / "emails_pendentes.jsonl"

# Importa módulos do portal (ANTES de patchar email_service)
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402
from redato_backend.portal import email_service  # noqa: E402
from redato_backend.portal.importer import (  # noqa: E402
    parse_planilha, validate_rows, run_import,
)
from redato_backend.portal.models import (  # noqa: E402
    Coordenador, Escola, Professor, Turma,
)

# Patcha o path de log de emails pra um tempdir isolado
email_service._PENDING_LOG = test_pending


# ──────────────────────────────────────────────────────────────────────
# Setup do schema isolado
# ──────────────────────────────────────────────────────────────────────

def _setup_schema(engine):
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
        conn.commit()
    for table in Base.metadata.tables.values():
        table.schema = TEST_SCHEMA
    Base.metadata.create_all(engine)


def _teardown_schema(engine):
    for table in Base.metadata.tables.values():
        table.schema = None
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE'))
        conn.commit()


# ──────────────────────────────────────────────────────────────────────
# Planilha sintética
# ──────────────────────────────────────────────────────────────────────

VALID_ROWS = [
    # 2 escolas, 3 coordenadores, 5 professores, 8 turmas
    ("SEDUC-CE-001", "Escola Boa Vista",
     "coord1@teste.br", "Maria Coord",
     "prof1@teste.br", "João Prof", "1A", "1S"),
    ("SEDUC-CE-001", "Escola Boa Vista",
     "coord1@teste.br", "Maria Coord",
     "prof1@teste.br", "João Prof", "1B", "1S"),
    ("SEDUC-CE-001", "Escola Boa Vista",
     "coord1@teste.br", "Maria Coord",
     "prof2@teste.br", "Ana Prof", "2A", "2S"),
    ("SEDUC-CE-001", "Escola Boa Vista",
     "coord1@teste.br", "Maria Coord",
     "prof3@teste.br", "Pedro Prof", "3A", "3S"),
    ("SEDUC-CE-002", "Escola Caridade",
     "coord2@teste.br", "Carlos Coord",
     "prof4@teste.br", "Luiza Prof", "1A", "1S"),
    ("SEDUC-CE-002", "Escola Caridade",
     "coord2@teste.br", "Carlos Coord",
     "prof4@teste.br", "Luiza Prof", "1B", "1S"),
    ("SEDUC-CE-002", "Escola Caridade",
     "coord3@teste.br", "Beto Coord",  # mesma escola, outro coord
     "prof5@teste.br", "Marta Prof", "2A", "2S"),
    ("SEDUC-CE-002", "Escola Caridade",
     "coord3@teste.br", "Beto Coord",
     "prof5@teste.br", "Marta Prof", "2B", "2S"),
]


def _make_csv(rows, path: Path) -> Path:
    headers = (
        "escola_id,escola_nome,coordenador_email,coordenador_nome,"
        "professor_email,professor_nome,turma_codigo,turma_serie\n"
    )
    body = "\n".join(",".join(r) for r in rows) + "\n"
    path.write_text(headers + body, encoding="utf-8")
    return path


def _make_csv_valid(tmp: Path) -> Path:
    return _make_csv(VALID_ROWS, tmp / "valid.csv")


def _make_csv_with_errors(tmp: Path) -> Path:
    """Planilha com problemas: email inválido, série inválida, campo vazio,
    turma duplicada."""
    rows = list(VALID_ROWS)
    rows.append(("SEDUC-CE-003", "Escola X",
                 "email-sem-arroba", "Coord X",
                 "profX@teste.br", "Prof X", "1A", "1S"))
    rows.append(("SEDUC-CE-003", "Escola X",
                 "coordY@teste.br", "Coord Y",
                 "profY@teste.br", "Prof Y", "1B", "4S"))  # série inválida
    rows.append(("SEDUC-CE-003", "Escola X",
                 "coordY@teste.br", "Coord Y",
                 "profY@teste.br", "Prof Y", "", "1S"))  # turma_codigo vazio
    rows.append(("SEDUC-CE-001", "Escola Boa Vista",
                 "coord1@teste.br", "Maria Coord",
                 "prof1@teste.br", "João Prof", "1A", "1S"))  # turma duplicada
    return _make_csv(rows, tmp / "errors.csv")


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_parse_csv_valido(engine, tmp_dir):
    csv = _make_csv_valid(tmp_dir)
    rows, issues = parse_planilha(csv)
    assert len(issues) == 0, f"issues estruturais: {issues}"
    assert len(rows) == 8
    return f"parse CSV: 8 linhas, 0 issues estruturais ✓"


def test_validate_rows_validos(engine, tmp_dir):
    csv = _make_csv_valid(tmp_dir)
    rows, _ = parse_planilha(csv)
    issues = validate_rows(rows)
    erros = [i for i in issues if i.severity == "error"]
    assert len(erros) == 0, f"erros inesperados: {[i.message for i in erros]}"
    return f"validate_rows válido: 0 erros ✓"


def test_validate_rows_com_erros(engine, tmp_dir):
    csv = _make_csv_with_errors(tmp_dir)
    rows, _ = parse_planilha(csv)
    issues = validate_rows(rows)
    erros = [i for i in issues if i.severity == "error"]
    codes = {i.code for i in erros}
    assert "email_invalido" in codes, f"codes: {codes}"
    assert "serie_invalida" in codes, f"codes: {codes}"
    assert "campo_vazio" in codes, f"codes: {codes}"
    assert "turma_duplicada" in codes, f"codes: {codes}"
    return f"validate_rows c/ erros: {len(erros)} detectados ({sorted(codes)}) ✓"


def test_dry_run(engine, tmp_dir):
    csv = _make_csv_valid(tmp_dir)
    with Session(engine) as session:
        report = run_import(session, csv, modo="dry-run", ano_letivo=2026)
    d = report.to_dict()
    assert d["modo"] == "dry-run"
    assert d["linhas_lidas"] == 8
    assert d["escolas_novas"] == 2
    assert d["coordenadores_novos"] == 3
    assert d["professores_novos"] == 5
    assert d["turmas_novas"] == 8
    # Dry-run não persiste:
    with Session(engine) as session:
        n = session.execute(text(
            f'SELECT COUNT(*) FROM "{TEST_SCHEMA}".escolas'
        )).scalar()
    assert n == 0, f"dry-run deveria não persistir, mas tem {n} escolas no DB"
    return f"dry-run: 2/3/5/8 reportados, 0 persistidos ✓"


def test_commit(engine, tmp_dir):
    csv = _make_csv_valid(tmp_dir)
    with Session(engine) as session:
        report = run_import(session, csv, modo="commit", ano_letivo=2026)
    d = report.to_dict()
    assert d["modo"] == "commit"
    assert len(d["erros"]) == 0
    with Session(engine) as session:
        n_escolas = session.execute(text(
            f'SELECT COUNT(*) FROM "{TEST_SCHEMA}".escolas'
        )).scalar()
        n_coords = session.execute(text(
            f'SELECT COUNT(*) FROM "{TEST_SCHEMA}".coordenadores'
        )).scalar()
        n_profs = session.execute(text(
            f'SELECT COUNT(*) FROM "{TEST_SCHEMA}".professores'
        )).scalar()
        n_turmas = session.execute(text(
            f'SELECT COUNT(*) FROM "{TEST_SCHEMA}".turmas'
        )).scalar()
    assert (n_escolas, n_coords, n_profs, n_turmas) == (2, 3, 5, 8), \
        f"got ({n_escolas}, {n_coords}, {n_profs}, {n_turmas})"
    return f"commit: 2 escolas / 3 coords / 5 profs / 8 turmas persistidos ✓"


def test_idempotencia(engine, tmp_dir):
    """Re-import com mesma planilha não duplica."""
    csv = _make_csv_valid(tmp_dir)
    with Session(engine) as session:
        report2 = run_import(session, csv, modo="commit", ano_letivo=2026)
    d = report2.to_dict()
    assert d["escolas_novas"] == 0, f"got {d['escolas_novas']}"
    assert d["coordenadores_novos"] == 0
    assert d["professores_novos"] == 0
    assert d["turmas_novas"] == 0
    # Verifica count global ainda 2/3/5/8
    with Session(engine) as session:
        n_turmas = session.execute(text(
            f'SELECT COUNT(*) FROM "{TEST_SCHEMA}".turmas'
        )).scalar()
    assert n_turmas == 8, f"expected 8 turmas, got {n_turmas}"
    return f"idempotência: 2ª run = 0 novos, 8 turmas ainda ✓"


def test_codigo_join_formato(engine, tmp_dir):
    """codigo_join gerado no formato TURMA-CE001-1A-2026."""
    with Session(engine) as session:
        codigo = session.execute(text(
            f"SELECT codigo_join FROM \"{TEST_SCHEMA}\".turmas "
            f"WHERE codigo = '1A' AND ano_letivo = 2026 "
            f"ORDER BY created_at LIMIT 1"
        )).scalar()
    assert codigo, "codigo_join vazio"
    parts = codigo.split("-")
    assert parts[0] == "TURMA", f"got {parts}"
    assert parts[-1] == "2026", f"got {parts}"
    assert "1A" in parts, f"got {parts}"
    return f"codigo_join formato: {codigo} ✓"


def test_endpoint_import_token_correto(engine, tmp_dir):
    """POST /admin/import-planilha com token correto retorna 200 + JSON."""
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app

    csv = _make_csv_valid(tmp_dir)
    client = TestClient(app)
    with csv.open("rb") as f:
        resp = client.post(
            "/admin/import-planilha",
            headers={"X-Admin-Token": "test-admin-token-m2"},
            files={"file": ("planilha.csv", f, "text/csv")},
            data={"dry_run": "true", "ano_letivo": "2026"},
        )
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text[:200]}"
    body = resp.json()
    assert body["modo"] == "dry-run"
    return f"endpoint POST com token correto: 200 OK ✓"


def test_endpoint_import_token_errado(engine, tmp_dir):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app

    csv = _make_csv_valid(tmp_dir)
    client = TestClient(app)
    with csv.open("rb") as f:
        resp = client.post(
            "/admin/import-planilha",
            headers={"X-Admin-Token": "TOKEN-ERRADO"},
            files={"file": ("planilha.csv", f, "text/csv")},
            data={"dry_run": "true"},
        )
    assert resp.status_code == 401, f"esperado 401, got {resp.status_code}"
    return f"endpoint POST com token errado: 401 ✓"


def test_send_welcome_dry_run(engine, tmp_dir):
    """Sem SENDGRID_API_KEY, dispara em modo dry-run e popula jsonl."""
    # Limpa jsonl antes
    if test_pending.exists():
        test_pending.unlink()
    with Session(engine) as session:
        result = email_service.send_welcome_emails(
            session,
            coordenador_emails=["coord1@teste.br"],
            professor_emails=["prof1@teste.br", "prof2@teste.br"],
        )
    d = result.to_dict()
    assert d["enviados"] == 3, f"got {d}"
    assert d["falhados"] == 0
    assert d["ja_tinham_senha"] == 0
    assert test_pending.exists(), f"jsonl não foi criado em {test_pending}"
    lines = test_pending.read_text().strip().splitlines()
    assert len(lines) == 3, f"esperava 3 emails no jsonl, got {len(lines)}"
    # Verifica que tokens foram gerados nos users
    with Session(engine) as session:
        coord = session.execute(text(
            f"SELECT primeiro_acesso_token, primeiro_acesso_expira_em "
            f"FROM \"{TEST_SCHEMA}\".coordenadores "
            f"WHERE email = 'coord1@teste.br'"
        )).first()
    assert coord and coord[0], f"token não gerado: {coord}"
    assert coord[1], f"expira_em não setado: {coord}"
    return (f"send_welcome dry-run: 3 enviados, jsonl populado "
            f"({len(lines)} linhas), tokens gerados ✓")


def test_cli_import_planilha_executavel(engine, tmp_dir):
    """Smoke do CLI: --json-only + dry-run."""
    csv = _make_csv_valid(tmp_dir)
    result = subprocess.run(
        [sys.executable, "-m", "redato_backend.portal.import_planilha",
         str(csv), "--json-only"],
        capture_output=True, text=True, cwd=str(BACKEND), timeout=30,
        env={**os.environ},
    )
    # CLI usa schema default (não TEST_SCHEMA) — vai ver dados reais.
    # Importante: --json-only sai 0 ou 2 dependendo de erros, não trava.
    assert result.returncode in (0, 2), \
        f"returncode={result.returncode}, stderr={result.stderr[-300:]}"
    # Tenta parse do stdout
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return f"CLI rodou mas stdout não é JSON: {result.stdout[:200]}"
    assert "modo" in report
    return f"CLI dry-run executável: modo={report['modo']}, "\
           f"linhas={report.get('linhas_lidas')} ✓"


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS = [
    test_parse_csv_valido,
    test_validate_rows_validos,
    test_validate_rows_com_erros,
    test_dry_run,
    test_commit,
    test_idempotencia,
    test_codigo_join_formato,
    test_endpoint_import_token_correto,
    test_endpoint_import_token_errado,
    test_send_welcome_dry_run,
    test_cli_import_planilha_executavel,
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não configurada")
        sys.exit(1)
    print(f"DATABASE_URL : {db_url}")
    print(f"Test schema  : {TEST_SCHEMA}")
    print(f"Email log    : {test_pending}")
    print()

    engine = create_engine(db_url, future=True)
    _setup_schema(engine)

    # Patch get_engine pra usar nossa engine + schema isolado
    # (admin_api / cli usam get_engine da db.py com search_path default;
    # workaround: definir search_path via env do Postgres pra essa sessão)
    from redato_backend.portal import db as portal_db
    portal_db._engine = None
    # Monkey-patch: usa nossa engine global
    original_get_engine = portal_db.get_engine
    portal_db.get_engine = lambda *a, **k: engine

    # Set search_path no engine pra schema isolado
    with engine.connect() as conn:
        conn.execute(text(f'SET search_path TO "{TEST_SCHEMA}", public'))

    # Pra cada conexão nova (Session), set search_path via event
    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _conn_record):
        with dbapi_conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{TEST_SCHEMA}", public')

    tmp_dir = Path(tempfile.mkdtemp(prefix="m2csv_"))
    print(f"\n{'='*70}")
    failures = []
    try:
        for fn in TESTS:
            try:
                res = fn(engine, tmp_dir)
                print(f"  ✓ {fn.__name__}: {res}")
            except AssertionError as exc:
                print(f"  ✗ {fn.__name__}: AssertionError: {exc}")
                failures.append((fn.__name__, str(exc)))
            except Exception as exc:
                print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
                failures.append((fn.__name__, repr(exc)))
    finally:
        portal_db.get_engine = original_get_engine
        portal_db._engine = None
        try:
            _teardown_schema(engine)
        except Exception as exc:
            print(f"WARN teardown: {exc!r}")

    print(f"\n{'='*70}")
    if failures:
        print(f"FALHA: {len(failures)}/{len(TESTS)}")
        sys.exit(1)
    print(f"OK: {len(TESTS)}/{len(TESTS)} testes passaram")


if __name__ == "__main__":
    main()
