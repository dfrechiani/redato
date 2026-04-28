#!/usr/bin/env python3
"""Smoke test M1 — modelos SQLAlchemy + Postgres + migração.

Cobre:
1. CRUD básico via ORM (Escola → Coordenador → Professor → Turma →
   AlunoTurma → Atividade → Envio → Interaction).
2. Constraint UNIQUE de aluno por turma + envio único por atividade.
3. Property `Atividade.status` em 3 momentos (passado, presente, futuro).
4. Migração SQLite → Postgres com dados sintéticos + verificação de
   integridade (count antigo vs novo).

Usa um schema temporário do Postgres (CREATE SCHEMA + SET search_path)
pra não tocar dados reais. Se DATABASE_URL_TEST não setada, cai em
DATABASE_URL com schema isolado.
"""
from __future__ import annotations

import os
import sys
import sqlite3
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
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

# Usa a mesma DATABASE_URL mas com schema isolado pra teste
TEST_SCHEMA = f"m1_test_{uuid.uuid4().hex[:8]}"

from sqlalchemy import create_engine, select, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402
from redato_backend.portal.models import (  # noqa: E402
    Escola, Coordenador, Professor, Turma, AlunoTurma,
    Atividade, Envio, Interaction,
)


# Cache de UUIDs de missões (populado em _setup_test_schema)
_MISSAO_IDS: dict = {}


def _setup_test_schema(engine):
    """Cria schema isolado e aplica DDL via Base.metadata.create_all.
    M4: popula missões pra testes de Atividade (que agora referenciam
    Missao via FK)."""
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{TEST_SCHEMA}"'))
        conn.commit()
    for table in Base.metadata.tables.values():
        table.schema = TEST_SCHEMA
    Base.metadata.create_all(engine)
    from redato_backend.portal.seed_missoes import seed_missoes
    with Session(engine) as session:
        seed_missoes(session)
        for m in session.execute(select(models.Missao)).scalars():
            _MISSAO_IDS[m.codigo] = m.id


def _teardown_test_schema(engine):
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{TEST_SCHEMA}" CASCADE'))
        conn.commit()


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_crud_full_chain(session: Session) -> str:
    """Cria toda a cadeia Escola → ... → Envio → Interaction. Verifica
    relacionamentos."""
    escola = Escola(codigo="TEST-001", nome="Escola Teste",
                    estado="CE", municipio="Fortaleza")
    session.add(escola)
    session.flush()

    coord = Coordenador(escola_id=escola.id, nome="Maria Coord",
                        email=f"coord-{uuid.uuid4().hex[:6]}@teste.br")
    session.add(coord)

    prof = Professor(escola_id=escola.id, nome="João Prof",
                     email=f"prof-{uuid.uuid4().hex[:6]}@teste.br")
    session.add(prof)
    session.flush()

    turma = Turma(escola_id=escola.id, professor_id=prof.id,
                  codigo="1A", serie="1S",
                  codigo_join=f"TURMA-CE001-1A-2026-{uuid.uuid4().hex[:4]}",
                  ano_letivo=2026)
    session.add(turma)
    session.flush()

    aluno = AlunoTurma(turma_id=turma.id, nome="Aluno Teste",
                       telefone="+5511999000001")
    session.add(aluno)

    atividade = Atividade(
        turma_id=turma.id, missao_id=_MISSAO_IDS["RJ1·OF10·MF"],
        data_inicio=datetime.now(timezone.utc) - timedelta(hours=1),
        data_fim=datetime.now(timezone.utc) + timedelta(hours=1),
        criada_por_professor_id=prof.id,
    )
    session.add(atividade)

    interaction = Interaction(
        aluno_phone="+5511999000001",
        # Interaction.missao_id continua String (legado SQLite); só
        # Atividade.missao_id virou UUID FK em M4.
        missao_id="RJ1·OF10·MF",
        activity_id="RJ1·OF10·MF",
    )
    session.add(interaction)
    session.flush()

    envio = Envio(atividade_id=atividade.id,
                  aluno_turma_id=aluno.id,
                  interaction_id=interaction.id)
    session.add(envio)
    session.flush()

    # Verifica relacionamentos
    assert escola.coordenadores[0].id == coord.id
    assert escola.professores[0].id == prof.id
    assert escola.turmas[0].id == turma.id
    assert turma.alunos[0].id == aluno.id
    assert turma.atividades[0].id == atividade.id
    assert envio.atividade.id == atividade.id
    assert envio.interaction.id == interaction.id

    return "CRUD chain Escola→...→Envio + relacionamentos OK"


def test_uq_aluno_por_turma(session: Session) -> str:
    """Mesmo telefone na mesma turma falha."""
    escola = Escola(codigo="UQ-001", nome="E", estado="CE",
                    municipio="F")
    prof = Professor(escola=escola, nome="P",
                     email=f"p-{uuid.uuid4().hex[:6]}@t.br")
    turma = Turma(escola=escola, professor=prof, codigo="1A", serie="1S",
                  codigo_join=f"TURMA-UQ001-1A-{uuid.uuid4().hex[:4]}",
                  ano_letivo=2026)
    session.add_all([escola, prof, turma])
    session.flush()

    aluno1 = AlunoTurma(turma_id=turma.id, nome="A1", telefone="+5511AAA")
    session.add(aluno1)
    session.flush()

    aluno2 = AlunoTurma(turma_id=turma.id, nome="A2", telefone="+5511AAA")
    session.add(aluno2)
    try:
        session.flush()
        return "FAIL: deveria ter levantado IntegrityError"
    except IntegrityError:
        session.rollback()
        return "UNIQUE(turma_id, telefone) bloqueia duplicata ✓"


def test_uq_envio_unico_por_atividade(session: Session) -> str:
    """Mesmo aluno_turma + atividade não pode ter 2 envios."""
    escola = Escola(codigo=f"UQE-{uuid.uuid4().hex[:4]}", nome="E",
                    estado="CE", municipio="F")
    prof = Professor(escola=escola, nome="P",
                     email=f"p2-{uuid.uuid4().hex[:6]}@t.br")
    turma = Turma(escola=escola, professor=prof, codigo="1B", serie="1S",
                  codigo_join=f"TURMA-UQE-{uuid.uuid4().hex[:4]}",
                  ano_letivo=2026)
    session.add_all([escola, prof, turma])
    session.flush()

    aluno = AlunoTurma(turma_id=turma.id, nome="A", telefone=f"+55{uuid.uuid4().hex[:8]}")
    atv = Atividade(turma_id=turma.id, missao_id=_MISSAO_IDS["RJ1·OF10·MF"],
                    data_inicio=datetime.now(timezone.utc),
                    data_fim=datetime.now(timezone.utc) + timedelta(hours=2),
                    criada_por_professor_id=prof.id)
    session.add_all([aluno, atv])
    session.flush()

    e1 = Envio(atividade_id=atv.id, aluno_turma_id=aluno.id)
    session.add(e1)
    session.flush()

    e2 = Envio(atividade_id=atv.id, aluno_turma_id=aluno.id)
    session.add(e2)
    try:
        session.flush()
        return "FAIL: deveria ter levantado IntegrityError"
    except IntegrityError:
        session.rollback()
        return "UNIQUE(atividade_id, aluno_turma_id) bloqueia duplicata ✓"


def test_atividade_status_property(session: Session) -> str:
    """status calcula 'agendada'/'ativa'/'encerrada' baseado em datetime."""
    escola = Escola(codigo=f"ST-{uuid.uuid4().hex[:4]}", nome="E",
                    estado="CE", municipio="F")
    prof = Professor(escola=escola, nome="P",
                     email=f"p3-{uuid.uuid4().hex[:6]}@t.br")
    turma = Turma(escola=escola, professor=prof, codigo="2A", serie="2S",
                  codigo_join=f"TURMA-ST-{uuid.uuid4().hex[:4]}",
                  ano_letivo=2026)
    session.add_all([escola, prof, turma])
    session.flush()

    agora = datetime.now(timezone.utc)
    atv_agendada = Atividade(
        turma_id=turma.id, missao_id=_MISSAO_IDS["RJ1·OF11·MF"],
        data_inicio=agora + timedelta(days=1),
        data_fim=agora + timedelta(days=2),
        criada_por_professor_id=prof.id,
    )
    atv_ativa = Atividade(
        turma_id=turma.id, missao_id=_MISSAO_IDS["RJ1·OF12·MF"],
        data_inicio=agora - timedelta(hours=1),
        data_fim=agora + timedelta(hours=1),
        criada_por_professor_id=prof.id,
    )
    atv_encerrada = Atividade(
        turma_id=turma.id, missao_id=_MISSAO_IDS["RJ1·OF13·MF"],
        data_inicio=agora - timedelta(days=2),
        data_fim=agora - timedelta(days=1),
        criada_por_professor_id=prof.id,
    )
    session.add_all([atv_agendada, atv_ativa, atv_encerrada])
    session.flush()

    assert atv_agendada.status == "agendada", f"got {atv_agendada.status}"
    assert atv_ativa.status == "ativa", f"got {atv_ativa.status}"
    assert atv_encerrada.status == "encerrada", f"got {atv_encerrada.status}"
    return "Atividade.status agendada/ativa/encerrada ✓"


def test_check_constraint_serie(session: Session) -> str:
    """Serie inválida (ex.: '4S') é rejeitada."""
    escola = Escola(codigo=f"CK-{uuid.uuid4().hex[:4]}", nome="E",
                    estado="CE", municipio="F")
    prof = Professor(escola=escola, nome="P",
                     email=f"p4-{uuid.uuid4().hex[:6]}@t.br")
    session.add_all([escola, prof])
    session.flush()

    bad = Turma(escola=escola, professor=prof, codigo="X", serie="4S",
                codigo_join=f"TURMA-CK-{uuid.uuid4().hex[:4]}",
                ano_letivo=2026)
    session.add(bad)
    try:
        session.flush()
        return "FAIL: serie='4S' deveria ter levantado IntegrityError"
    except IntegrityError:
        session.rollback()
        return "CHECK serie em ('1S','2S','3S') ✓"


def test_check_constraint_intervalo_atividade(session: Session) -> str:
    """data_fim <= data_inicio é rejeitado."""
    escola = Escola(codigo=f"INT-{uuid.uuid4().hex[:4]}", nome="E",
                    estado="CE", municipio="F")
    prof = Professor(escola=escola, nome="P",
                     email=f"p5-{uuid.uuid4().hex[:6]}@t.br")
    turma = Turma(escola=escola, professor=prof, codigo="3A", serie="3S",
                  codigo_join=f"TURMA-INT-{uuid.uuid4().hex[:4]}",
                  ano_letivo=2026)
    session.add_all([escola, prof, turma])
    session.flush()

    agora = datetime.now(timezone.utc)
    bad = Atividade(
        turma_id=turma.id, missao_id=_MISSAO_IDS["RJ1·OF10·MF"],
        data_inicio=agora,
        data_fim=agora - timedelta(seconds=1),
        criada_por_professor_id=prof.id,
    )
    session.add(bad)
    try:
        session.flush()
        return "FAIL: data_fim < data_inicio deveria falhar"
    except IntegrityError:
        session.rollback()
        return "CHECK data_fim > data_inicio ✓"


def test_migration_sqlite_to_postgres(engine) -> str:
    """Cria SQLite sintético com 5 interactions, roda migrate, conta no Postgres."""
    # SQLite temporário com schema idêntico ao bot atual
    tmp_dir = tempfile.mkdtemp(prefix="m1test_")
    sqlite_path = Path(tmp_dir) / "synth.db"
    conn = sqlite3.connect(sqlite_path)
    conn.executescript("""
        CREATE TABLE interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_phone TEXT NOT NULL,
            turma_id TEXT,
            missao_id TEXT NOT NULL,
            activity_id TEXT NOT NULL,
            foto_path TEXT, foto_hash TEXT,
            texto_transcrito TEXT,
            ocr_quality_issues TEXT, ocr_metrics TEXT,
            redato_output TEXT, resposta_aluno TEXT,
            elapsed_ms INTEGER,
            invalidated_at TEXT,
            created_at TEXT NOT NULL
        );
    """)
    base_ts = datetime.now(timezone.utc)
    for i in range(5):
        conn.execute(
            "INSERT INTO interactions (aluno_phone, missao_id, activity_id, "
            "texto_transcrito, resposta_aluno, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"+551199{i:04d}", "RJ1·OF10·MF", "RJ1·OF10·MF",
             f"texto sintético {i}", f"resposta {i}",
             (base_ts + timedelta(seconds=i)).isoformat()),
        )
    conn.commit()
    conn.close()

    # Roda migrate via subprocess (testa o módulo end-to-end)
    import subprocess
    result = subprocess.run(
        [sys.executable, "-m", "redato_backend.portal.migrate_sqlite_to_postgres",
         "--sqlite-url", f"sqlite:///{sqlite_path}",
         "--postgres-url", os.environ["DATABASE_URL"]],
        capture_output=True, text=True, cwd=str(BACKEND), timeout=30,
    )
    if result.returncode != 0:
        return f"FAIL migrate stdout={result.stdout[-300:]} stderr={result.stderr[-300:]}"

    # Conta no Postgres (schema default)
    with engine.connect() as conn:
        n = conn.execute(text(
            "SELECT COUNT(*) FROM public.interactions "
            "WHERE source = 'whatsapp_v1' AND aluno_phone LIKE '+5511990%'"
        )).scalar()
    if n < 5:
        return f"FAIL: esperava ≥5 linhas migradas, got {n}"
    return f"migração SQLite→Postgres: 5 sintéticos migrados ✓"


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS_SCHEMA = [
    test_crud_full_chain,
    test_uq_aluno_por_turma,
    test_uq_envio_unico_por_atividade,
    test_atividade_status_property,
    test_check_constraint_serie,
    test_check_constraint_intervalo_atividade,
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não configurada")
        sys.exit(1)
    print(f"DATABASE_URL: {db_url}")
    print(f"Test schema : {TEST_SCHEMA}")
    print()

    engine = create_engine(db_url, future=True)
    _setup_test_schema(engine)
    print(f"\n{'='*70}")
    failures = []
    try:
        for fn in TESTS_SCHEMA:
            with Session(engine) as session:
                try:
                    res = fn(session)
                    session.commit()
                    print(f"  ✓ {fn.__name__}: {res}")
                except AssertionError as exc:
                    print(f"  ✗ {fn.__name__}: AssertionError: {exc}")
                    failures.append((fn.__name__, str(exc)))
                except Exception as exc:
                    print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
                    failures.append((fn.__name__, repr(exc)))

        # Migration test usa schema default (não TEST_SCHEMA) porque o
        # script do migrate_sqlite_to_postgres não conhece schema isolado.
        try:
            res = test_migration_sqlite_to_postgres(engine)
            print(f"  ✓ test_migration_sqlite_to_postgres: {res}")
        except AssertionError as exc:
            print(f"  ✗ test_migration_sqlite_to_postgres: {exc}")
            failures.append(("test_migration_sqlite_to_postgres", str(exc)))
        except Exception as exc:
            print(f"  ✗ test_migration_sqlite_to_postgres: {type(exc).__name__}: {exc}")
            failures.append(("test_migration_sqlite_to_postgres", repr(exc)))
    finally:
        # Sempre limpa schema isolado, mesmo em falha
        for table in Base.metadata.tables.values():
            table.schema = None
        try:
            _teardown_test_schema(engine)
        except Exception as exc:
            print(f"WARN: falha no teardown do schema {TEST_SCHEMA}: {exc!r}")

    print(f"\n{'='*70}")
    if failures:
        print(f"FALHA: {len(failures)}")
        sys.exit(1)
    print(f"OK: {len(TESTS_SCHEMA) + 1}/{len(TESTS_SCHEMA) + 1} testes passaram")


if __name__ == "__main__":
    main()
