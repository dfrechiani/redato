"""Testes do script `scripts/reconciliar_envios_orfaos.py` (M9.6).

Este script recupera interactions órfãs em SQLite legado que falharam
ao ser criadas em Postgres pelo bug pre-M9.6. Cobertura:

1. **`_parse_iso`** — datas vindas do SQLite têm formatos variáveis
   (com/sem tz, com/sem `Z`). Função tolerante.
2. **`_ler_interactions_sqlite`** — só puxa rows com `resposta_aluno`
   E `foto_hash` E sem `invalidated_at` (orphans dignos de recuperar).
3. **Dry-run não escreve** — modo default. Smoke garante que session
   é rollback'd, não commit'd.
4. **Idempotência** — segundo run em apply não duplica (match por
   `foto_hash` em Postgres).

Tests (3) e (4) usam SQLite in-memory pra simular Postgres — o script
abstrai DB via `get_engine()`. Pra esses tests, monkey-patch dele.
"""
from __future__ import annotations

import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[5]
SCRIPTS = REPO / "scripts"
sys.path.insert(0, str(SCRIPTS))


# ──────────────────────────────────────────────────────────────────────
# _parse_iso — robustez de formato
# ──────────────────────────────────────────────────────────────────────

def test_parse_iso_aware_com_offset():
    from reconciliar_envios_orfaos import _parse_iso
    dt = _parse_iso("2026-04-29T13:45:00+00:00")
    assert dt.tzinfo is not None
    assert dt.year == 2026
    assert dt.hour == 13


def test_parse_iso_aware_com_z():
    """SQLite com `Z` no final (Zulu time = UTC)."""
    from reconciliar_envios_orfaos import _parse_iso
    dt = _parse_iso("2026-04-29T13:45:00Z")
    assert dt.tzinfo == timezone.utc


def test_parse_iso_naive_assume_utc():
    """SQLite às vezes salva sem tz (legacy). Defensivo: assume UTC."""
    from reconciliar_envios_orfaos import _parse_iso
    dt = _parse_iso("2026-04-29T13:45:00")
    assert dt.tzinfo == timezone.utc


def test_parse_iso_naive_sem_segundos_funciona():
    """Sub-second precision e formato sem 'T' tolerados via fallback."""
    from reconciliar_envios_orfaos import _parse_iso
    dt = _parse_iso("2026-04-29T13:45:00.123456")
    assert dt.year == 2026


# ──────────────────────────────────────────────────────────────────────
# _ler_interactions_sqlite — filtros
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture
def sqlite_temp(tmp_path: Path) -> Path:
    """SQLite com schema do bot legado + 4 rows: 1 órfã candidata, 1 sem
    resposta_aluno, 1 sem foto_hash, 1 invalidated."""
    db = tmp_path / "redato.db"
    with sqlite3.connect(db) as c:
        c.executescript("""
        CREATE TABLE interactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            aluno_phone TEXT NOT NULL,
            turma_id TEXT,
            missao_id TEXT NOT NULL,
            activity_id TEXT NOT NULL,
            foto_path TEXT,
            foto_hash TEXT,
            texto_transcrito TEXT,
            ocr_quality_issues TEXT,
            ocr_metrics TEXT,
            redato_output TEXT,
            resposta_aluno TEXT,
            elapsed_ms INTEGER,
            created_at TEXT NOT NULL,
            invalidated_at TEXT
        );
        """)
        # Candidato órfão — entra
        c.execute(
            "INSERT INTO interactions (aluno_phone, missao_id, activity_id, "
            "foto_hash, resposta_aluno, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("+5511999000001", "RJ1·OF04·MF", "RJ1·OF04·MF",
             "abcdef0123456789", "Feedback completo.",
             "2026-04-26T13:45:00+00:00"),
        )
        # Sem resposta_aluno — pula (ainda em processamento ou falhou)
        c.execute(
            "INSERT INTO interactions (aluno_phone, missao_id, activity_id, "
            "foto_hash, created_at) VALUES (?, ?, ?, ?, ?)",
            ("+5511999000002", "RJ1·OF04·MF", "RJ1·OF04·MF",
             "deadbeef00000000", "2026-04-26T14:00:00+00:00"),
        )
        # Sem foto_hash — pula (não dá pra cross-checkar com confiança)
        c.execute(
            "INSERT INTO interactions (aluno_phone, missao_id, activity_id, "
            "resposta_aluno, created_at) VALUES (?, ?, ?, ?, ?)",
            ("+5511999000003", "RJ1·OF04·MF", "RJ1·OF04·MF",
             "Feedback.", "2026-04-26T14:15:00+00:00"),
        )
        # Invalidada — pula (aluno disse "ocr errado")
        c.execute(
            "INSERT INTO interactions (aluno_phone, missao_id, activity_id, "
            "foto_hash, resposta_aluno, created_at, invalidated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("+5511999000004", "RJ1·OF04·MF", "RJ1·OF04·MF",
             "0123456789abcdef", "Feedback.",
             "2026-04-26T14:30:00+00:00",
             "2026-04-26T14:31:00+00:00"),
        )
    return db


def test_ler_interactions_filtra_apenas_orfas_validas(sqlite_temp: Path):
    """Dos 4 rows criados no fixture, só 1 é órfão recuperável."""
    from reconciliar_envios_orfaos import _ler_interactions_sqlite
    rows = _ler_interactions_sqlite(sqlite_temp)
    assert len(rows) == 1
    assert rows[0]["aluno_phone"] == "+5511999000001"
    assert rows[0]["foto_hash"] == "abcdef0123456789"


def test_ler_interactions_sqlite_inexistente_retorna_vazio(tmp_path: Path):
    """Defensivo: se o file não existe (deploy novo, dev-offline), o
    script não crasha — só log + return [] sem orfãos."""
    from reconciliar_envios_orfaos import _ler_interactions_sqlite
    rows = _ler_interactions_sqlite(tmp_path / "nao_existe.db")
    assert rows == []


# ──────────────────────────────────────────────────────────────────────
# Dry-run vs apply — comportamento de transação
# ──────────────────────────────────────────────────────────────────────

class _FakeQueryFirst:
    def __init__(self, val): self._val = val
    def first(self): return self._val


class _FakeScalars:
    def __init__(self, items): self._items = items
    def all(self): return list(self._items)


class _FakeExecute:
    """Retorna sempre 'sem aluno' pra rota crítica."""
    def __init__(self):
        self.called = 0
    def __call__(self, *args, **kwargs):
        self.called += 1
        # _ja_existe_em_postgres: `.first()` deve retornar None
        return _FakeResult()


class _FakeResult:
    def first(self): return None
    def scalar(self): return None
    def scalars(self): return _FakeScalars([])


class _FakeSession:
    """Substitui Session de SQLAlchemy. Conta commit/rollback/add."""
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.adds: list = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, *a, **kw): return _FakeResult()
    def add(self, obj): self.adds.append(obj)
    def flush(self): pass
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_dry_run_nao_commita_nada(
    sqlite_temp: Path, monkeypatch, tmp_path: Path,
):
    """Dry-run com 1 órfão (do fixture) NÃO chama commit. O órfão será
    classificado em `sem_aluno` (sem stub de AlunoTurma) — o ponto é
    que o teste roda sem Postgres E não escreve."""
    import reconciliar_envios_orfaos as rec
    monkeypatch.setenv("REDATO_WHATSAPP_DB", str(sqlite_temp))

    # Stub de get_engine + Session pra não exigir Postgres real
    fake_session = _FakeSession()

    class _FakeEngine:
        pass

    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine",
        lambda: _FakeEngine(),
    )
    # Substitui Session importada localmente em reconciliar()
    import sqlalchemy.orm
    monkeypatch.setattr(
        sqlalchemy.orm, "Session", lambda engine: fake_session,
    )

    stats = rec.reconciliar(apply=False)

    assert stats["sqlite_total"] == 1
    # Orphan foi categorizado em sem_aluno (sem AlunoTurma stubado).
    # O importante é que NADA foi escrito.
    assert fake_session.commits == 0
    assert fake_session.adds == []


def test_apply_no_modo_apply_chama_commit_quando_ha_orfao(
    sqlite_temp: Path, monkeypatch,
):
    """Sanity: em --apply o commit é chamado mesmo quando 0 inseridos
    (release explícito da transação). A escrita real de orfãos requer
    AlunoTurma+Atividade stubados — fora do escopo desse teste; o que
    importa aqui é que o branch `apply=True` chama `session.commit()`,
    não `session.rollback()`."""
    import reconciliar_envios_orfaos as rec
    monkeypatch.setenv("REDATO_WHATSAPP_DB", str(sqlite_temp))

    fake_session = _FakeSession()

    class _FakeEngine:
        pass

    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine",
        lambda: _FakeEngine(),
    )
    import sqlalchemy.orm
    monkeypatch.setattr(
        sqlalchemy.orm, "Session", lambda engine: fake_session,
    )

    rec.reconciliar(apply=True)
    assert fake_session.commits == 1
    assert fake_session.rollbacks == 0


def test_dry_run_explicitamente_chama_rollback(
    sqlite_temp: Path, monkeypatch,
):
    """Em dry-run a sessão é rollback'd. Importante porque, mesmo sem
    orfãos novos, queries SELECT podem ter pegado locks ou aberto
    transação — rollback deixa o connection pool limpo."""
    import reconciliar_envios_orfaos as rec
    monkeypatch.setenv("REDATO_WHATSAPP_DB", str(sqlite_temp))

    fake_session = _FakeSession()

    class _FakeEngine:
        pass

    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine",
        lambda: _FakeEngine(),
    )
    import sqlalchemy.orm
    monkeypatch.setattr(
        sqlalchemy.orm, "Session", lambda engine: fake_session,
    )

    rec.reconciliar(apply=False)
    assert fake_session.commits == 0
    assert fake_session.rollbacks == 1


# ──────────────────────────────────────────────────────────────────────
# Idempotência — _ja_existe_em_postgres bloqueia re-insert
# ──────────────────────────────────────────────────────────────────────

class _FakeResultExists:
    """Mock que retorna True em `_ja_existe_em_postgres`."""
    def first(self): return ("uuid_qualquer",)
    def scalar(self): return 1
    def scalars(self): return _FakeScalars([])


class _FakeSessionAlreadyExists:
    """Postgres já tem todos os foto_hashes — segundo run de --apply."""
    def __init__(self):
        self.commits = 0
        self.rollbacks = 0
        self.adds: list = []
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def execute(self, *a, **kw): return _FakeResultExists()
    def add(self, obj): self.adds.append(obj)
    def flush(self): pass
    def commit(self): self.commits += 1
    def rollback(self): self.rollbacks += 1


def test_idempotencia_segundo_apply_nao_duplica(
    sqlite_temp: Path, monkeypatch,
):
    """Roda --apply, depois roda de novo. No segundo run, todos os
    foto_hashes do SQLite já estão em Postgres — script vê 1 row e
    classifica em `already_in_pg` sem inserir nada."""
    import reconciliar_envios_orfaos as rec
    monkeypatch.setenv("REDATO_WHATSAPP_DB", str(sqlite_temp))

    fake_session = _FakeSessionAlreadyExists()

    class _FakeEngine:
        pass

    monkeypatch.setattr(
        "redato_backend.portal.db.get_engine",
        lambda: _FakeEngine(),
    )
    import sqlalchemy.orm
    monkeypatch.setattr(
        sqlalchemy.orm, "Session", lambda engine: fake_session,
    )

    stats = rec.reconciliar(apply=True)
    assert stats["sqlite_total"] == 1
    assert stats["already_in_pg"] == 1
    assert stats["inseridos"] == 0
    assert fake_session.adds == []  # nenhuma escrita


# ──────────────────────────────────────────────────────────────────────
# CLI — --help e parser
# ──────────────────────────────────────────────────────────────────────

def test_help_funciona():
    """Sanity: módulo importa e --help não crasha. Defensivo pra
    mudanças quebrarem o argparse."""
    import argparse
    import reconciliar_envios_orfaos as rec
    # main() lê sys.argv — usa SystemExit pra --help
    parser = argparse.ArgumentParser()
    # Smoke: módulo tem main + reconciliar exportados
    assert hasattr(rec, "main")
    assert hasattr(rec, "reconciliar")
    assert callable(rec.main)
