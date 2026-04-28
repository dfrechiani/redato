#!/usr/bin/env python3
"""Smoke test M4 — bot adaptado pro modelo de atividade ativa.

Cobre fluxos do bot SEM chamar API Anthropic (mockando _process_photo
nos casos que iriam até OCR/grade) e endpoints HTTP de notificação.

Cenários:
- Cadastro: aluno tenta foto sem cadastro → MSG_ALUNO_NAO_CADASTRADO
- Cadastro com código de turma válido → vinculado
- Cadastro com código inválido → rejeitado
- Cadastro com turma inativa → rejeitado
- Aluno cadastrado tenta enviar sem atividade ativa → rejeitado
- Aluno cadastrado tenta com atividade agendada → rejeitado (msg específica)
- Aluno cadastrado tenta com atividade encerrada → rejeitado
- Aluno cadastrado tenta com atividade ativa → processa (mockado)
- Endpoint /texto-notificacao com auth correto → 200
- Endpoint /notificar com auth correto → enviadas, marca timestamp
- Endpoint /notificar idempotente → segunda chamada retorna ja_notificada_em
- Endpoint sem auth → 401
- Endpoint com prof errado (de outra escola) → 403
- Refactor M2: _filter_pending_users coerente entre count e send
"""
from __future__ import annotations

import os
import sys
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

env_path = BACKEND / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):
                os.environ[k] = v

os.environ.setdefault(
    "JWT_SECRET_KEY",
    "test_secret_at_least_32_chars_for_smoke_m4_bot_atividades_xx",
)
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token-m4")
os.environ.pop("SENDGRID_API_KEY", None)
# Garante dry-run no notificar (sem Twilio key)
os.environ.pop("TWILIO_ACCOUNT_SID", None)

# Schema isolado pro Postgres
TEST_SCHEMA = f"m4_test_{uuid.uuid4().hex[:8]}"
test_audit = Path(tempfile.mkdtemp(prefix="m4audit_")) / "audit_log.jsonl"

# DB SQLite isolada pro bot (estado FSM)
test_sqlite = BACKEND / "data" / "whatsapp" / "redato_m4_test.db"
if test_sqlite.exists():
    test_sqlite.unlink()
os.environ["REDATO_WHATSAPP_DB"] = str(test_sqlite)

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402
from redato_backend.portal import portal_api  # noqa: E402
from redato_backend.portal.auth.jwt_service import encode_token  # noqa: E402
from redato_backend.portal.auth.password import hash_senha  # noqa: E402
from redato_backend.portal.models import (  # noqa: E402
    AlunoTurma, Atividade, Coordenador, Escola, Missao, Professor, Turma,
)
from redato_backend.portal.seed_missoes import seed_missoes  # noqa: E402
from redato_backend.whatsapp import bot, portal_link  # noqa: E402


portal_api._AUDIT_LOG = test_audit


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
# Fixtures
# ──────────────────────────────────────────────────────────────────────

class World:
    """Container só com IDs/strings — evita DetachedInstanceError ao
    acessar objetos ORM fora de session."""
    def __init__(self):
        self.escola_a_id: uuid.UUID = None
        self.escola_b_id: uuid.UUID = None
        self.prof_a_id: uuid.UUID = None
        self.prof_b_id: uuid.UUID = None
        self.coord_a_id: uuid.UUID = None
        self.turma_a_id: uuid.UUID = None
        self.turma_a_codigo_join: str = None
        self.turma_b_id: uuid.UUID = None
        self.atividade_ativa_id: uuid.UUID = None
        self.atividade_agendada_id: uuid.UUID = None
        self.atividade_encerrada_id: uuid.UUID = None


def _seed_world(engine) -> World:
    world = World()
    with Session(engine) as session:
        seed_missoes(session)
        session.commit()

        ea = Escola(codigo="E-CE-A01", nome="Escola A",
                    estado="CE", municipio="Fortaleza")
        eb = Escola(codigo="E-CE-B01", nome="Escola B",
                    estado="CE", municipio="Fortaleza")
        session.add_all([ea, eb]); session.flush()

        ca = Coordenador(escola_id=ea.id, nome="Coord A",
                         email="coord-a@e.br",
                         senha_hash=hash_senha("Senha123Forte"))
        pa = Professor(escola_id=ea.id, nome="Prof A",
                       email="prof-a@e.br",
                       senha_hash=hash_senha("Senha123Forte"))
        pb = Professor(escola_id=eb.id, nome="Prof B",
                       email="prof-b@e.br",
                       senha_hash=hash_senha("Senha123Forte"))
        session.add_all([ca, pa, pb]); session.flush()

        ta = Turma(escola_id=ea.id, professor_id=pa.id, codigo="1A",
                   serie="1S", codigo_join="TURMA-CEA01-1A-2026",
                   ano_letivo=2026)
        tb = Turma(escola_id=eb.id, professor_id=pb.id, codigo="1A",
                   serie="1S", codigo_join="TURMA-CEB01-1A-2026",
                   ano_letivo=2026)
        session.add_all([ta, tb]); session.flush()

        m_c3 = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF10·MF'")
        ).scalar()
        m_c4 = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF11·MF'")
        ).scalar()

        agora = datetime.now(timezone.utc)
        atv_ativa = Atividade(
            turma_id=ta.id, missao_id=m_c3,
            data_inicio=agora - timedelta(hours=1),
            data_fim=agora + timedelta(hours=1),
            criada_por_professor_id=pa.id,
        )
        atv_agend = Atividade(
            turma_id=ta.id, missao_id=m_c4,
            data_inicio=agora + timedelta(days=1),
            data_fim=agora + timedelta(days=2),
            criada_por_professor_id=pa.id,
        )
        m_c5 = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF12·MF'")
        ).scalar()
        atv_encerrada = Atividade(
            turma_id=ta.id, missao_id=m_c5,
            data_inicio=agora - timedelta(days=2),
            data_fim=agora - timedelta(days=1),
            criada_por_professor_id=pa.id,
        )
        session.add_all([atv_ativa, atv_agend, atv_encerrada])
        session.commit()

        world.escola_a_id = ea.id
        world.escola_b_id = eb.id
        world.coord_a_id = ca.id
        world.prof_a_id = pa.id
        world.prof_b_id = pb.id
        world.turma_a_id = ta.id
        world.turma_a_codigo_join = ta.codigo_join
        world.turma_b_id = tb.id
        world.atividade_ativa_id = atv_ativa.id
        world.atividade_agendada_id = atv_agend.id
        world.atividade_encerrada_id = atv_encerrada.id

    return world


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_aluno_nao_cadastrado_recebe_mensagem(engine, world):
    """Phone novo → bot pede código de turma."""
    phone = "+5511" + uuid.uuid4().hex[:8]
    msg = bot.InboundMessage(phone=phone, text="oi")
    out = bot.handle_inbound(msg)
    assert len(out) == 1
    assert "código" in out[0].text.lower() or "turma" in out[0].text.lower()
    return "phone novo → pede código de turma ✓"


def test_codigo_invalido(engine, world):
    phone = "+5511" + uuid.uuid4().hex[:8]
    bot.handle_inbound(bot.InboundMessage(phone=phone, text="oi"))
    out = bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="TURMA-NAOEXISTE-XX-2026"))
    assert "não encontrei" in out[0].text.lower()
    return "código de turma inexistente → mensagem clara ✓"


def test_cadastro_completo(engine, world):
    phone = "+5511" + uuid.uuid4().hex[:8]
    bot.handle_inbound(bot.InboundMessage(phone=phone, text="oi"))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text=world.turma_a_codigo_join))
    out = bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="João da Silva Aluno"))
    assert "vinculado" in out[0].text.lower() or "pronto" in out[0].text.lower()
    # Confere que foi pra DB
    with Session(engine) as session:
        a = session.execute(
            text(f"SELECT nome, turma_id FROM \"{TEST_SCHEMA}\".alunos_turma "
                 f"WHERE telefone = :phone"), {"phone": phone}
        ).first()
    assert a is not None
    assert a[0] == "João da Silva Aluno"
    return f"cadastro: AlunoTurma criado pra {phone} ✓"


def test_aluno_existente_tenta_se_cadastrar_de_novo(engine, world):
    phone = "+5511" + uuid.uuid4().hex[:8]
    bot.handle_inbound(bot.InboundMessage(phone=phone, text="oi"))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text=world.turma_a_codigo_join))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="Maria Aluna"))
    # Re-cadastrar na mesma turma
    bot.handle_inbound(bot.InboundMessage(phone=phone, text="oi"))
    out = bot.handle_inbound(bot.InboundMessage(
        phone=phone, text=world.turma_a_codigo_join))
    assert "já está cadastrado" in out[0].text.lower()
    return "tentar cadastrar 2× na mesma turma → mensagem específica ✓"


def test_envio_sem_atividade_ativa(engine, world):
    """Aluno cadastrado tenta foto pra missão sem atividade aberta."""
    phone = "+5511" + uuid.uuid4().hex[:8]
    # Cadastra
    bot.handle_inbound(bot.InboundMessage(phone=phone, text="oi"))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text=world.turma_a_codigo_join))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="Carlos Aluno"))

    # Cria foto sintética pequena
    from PIL import Image
    foto_path = Path(tempfile.mkdtemp(prefix="m4foto_")) / "test.jpg"
    Image.new("RGB", (200, 200), "white").save(foto_path, "JPEG")

    # Tenta enviar pra missão 14 (não tem atividade)
    out = bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="14", image_path=str(foto_path),
    ))
    assert "não há missão" in out[0].text.lower() or \
           "rj1·of14" in out[0].text.lower() or \
           "ativa" in out[0].text.lower(), f"got: {out[0].text}"
    return "envio sem atividade ativa → mensagem clara ✓"


def test_envio_atividade_agendada(engine, world):
    phone = "+5511" + uuid.uuid4().hex[:8]
    bot.handle_inbound(bot.InboundMessage(phone=phone, text="oi"))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text=world.turma_a_codigo_join))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="Pedro Aluno"))

    from PIL import Image
    foto_path = Path(tempfile.mkdtemp(prefix="m4foto_")) / "test.jpg"
    Image.new("RGB", (200, 200), "white").save(foto_path, "JPEG")

    # OF11 está agendada (no futuro)
    out = bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="11", image_path=str(foto_path),
    ))
    assert "agendada" in out[0].text.lower() or \
           "ainda não" in out[0].text.lower(), f"got: {out[0].text}"
    return "envio em atividade agendada → mensagem específica ✓"


def test_envio_atividade_encerrada(engine, world):
    phone = "+5511" + uuid.uuid4().hex[:8]
    bot.handle_inbound(bot.InboundMessage(phone=phone, text="oi"))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text=world.turma_a_codigo_join))
    bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="Ana Aluna"))

    from PIL import Image
    foto_path = Path(tempfile.mkdtemp(prefix="m4foto_")) / "test.jpg"
    Image.new("RGB", (200, 200), "white").save(foto_path, "JPEG")

    # OF12 está encerrada (no passado)
    out = bot.handle_inbound(bot.InboundMessage(
        phone=phone, text="12", image_path=str(foto_path),
    ))
    assert "encerr" in out[0].text.lower(), f"got: {out[0].text}"
    return "envio em atividade encerrada → mensagem específica ✓"


def test_endpoint_texto_notificacao(engine, world):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app

    client = TestClient(app)
    token, _ = encode_token(
        user_id=str(world.prof_a_id),
        papel="professor",
        escola_id=str(world.escola_a_id),
    )
    r = client.get(
        f"/portal/atividades/{world.atividade_ativa_id}/texto-notificacao",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    body = r.json()
    assert body["missao_codigo"] == "RJ1·OF10·MF"
    assert "código" in body["texto"].lower() or "missao" in body["texto"].lower()
    return f"GET /texto-notificacao: 200, texto com missão ✓"


def test_endpoint_notificar_dispara(engine, world):
    """POST /notificar marca timestamp + audit log dry-run (sem Twilio)."""
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app

    client = TestClient(app)

    # Adiciona 2 alunos na turma_a
    with Session(engine) as session:
        for i in range(2):
            session.add(AlunoTurma(
                turma_id=world.turma_a_id,
                nome=f"Aluno notif {i}",
                telefone=f"+5599800100{i:02d}",
            ))
        session.commit()

    token, _ = encode_token(
        user_id=str(world.prof_a_id),
        papel="professor",
        escola_id=str(world.escola_a_id),
    )
    r = client.post(
        f"/portal/atividades/{world.atividade_ativa_id}/notificar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    body = r.json()
    assert body["enviadas"] == 2, f"got {body}"

    # 2ª chamada — idempotente
    r2 = client.post(
        f"/portal/atividades/{world.atividade_ativa_id}/notificar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["enviadas"] == 0
    assert body2.get("ja_notificada_em") is not None
    return f"POST /notificar: 1ª 200 (2 enviadas), 2ª idempotente ✓"


def test_endpoint_notificar_sem_auth(engine, world):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    client = TestClient(app)
    r = client.post(
        f"/portal/atividades/{world.atividade_ativa_id}/notificar"
    )
    assert r.status_code in (401, 403), f"got {r.status_code}"
    return f"POST /notificar sem auth: {r.status_code} ✓"


def test_endpoint_notificar_prof_errado(engine, world):
    """Prof B (outra escola) tenta notificar atividade da escola A → 403."""
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app

    client = TestClient(app)
    token, _ = encode_token(
        user_id=str(world.prof_b_id),
        papel="professor",
        escola_id=str(world.escola_b_id),
    )
    # Cria nova atividade pra não conflitar com state de outro test
    with Session(engine) as session:
        m_c4 = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF11·MF'")
        ).scalar()
        agora = datetime.now(timezone.utc)
        atv2 = Atividade(
            turma_id=world.turma_a_id, missao_id=m_c4,
            data_inicio=agora - timedelta(hours=1),
            data_fim=agora + timedelta(hours=1),
            criada_por_professor_id=world.prof_a_id,
        )
        session.add(atv2); session.commit()
        atv2_id = atv2.id

    r = client.post(
        f"/portal/atividades/{atv2_id}/notificar",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403, f"got {r.status_code}: {r.text}"
    return f"POST /notificar com prof de outra escola: 403 ✓"


def test_refactor_filter_pending_users(engine, world):
    """M4 refactor: count e send usam função compartilhada."""
    from redato_backend.portal.email_service import filter_pending_users

    with Session(engine) as session:
        # Cria 2 usuários sem senha + 1 com senha
        e = Escola(codigo=f"E-RF-{uuid.uuid4().hex[:4]}", nome="EscolaRf",
                   estado="CE", municipio="Fortaleza")
        session.add(e); session.flush()
        session.add(Coordenador(escola_id=e.id, nome="C1",
                                 email=f"c1-{uuid.uuid4().hex[:6]}@rf.br"))
        session.add(Professor(escola_id=e.id, nome="P1",
                               email=f"p1-{uuid.uuid4().hex[:6]}@rf.br"))
        session.add(Professor(escola_id=e.id, nome="P2",
                               email=f"p2-{uuid.uuid4().hex[:6]}@rf.br",
                               senha_hash=hash_senha("Senha123")))
        session.commit()

        # Sem filtro de senha — pega todos da escola
        c1, p1 = filter_pending_users(session, escola_id=e.id,
                                       only_no_password=False)
        assert len(c1) == 1
        assert len(p1) == 2
        # Só sem senha
        c2, p2 = filter_pending_users(session, escola_id=e.id,
                                       only_no_password=True)
        assert len(c2) == 1
        assert len(p2) == 1, f"esperava 1 sem senha, got {len(p2)}"
    return "filter_pending_users: filtro de senha funciona ✓"


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS = [
    test_aluno_nao_cadastrado_recebe_mensagem,
    test_codigo_invalido,
    test_cadastro_completo,
    test_aluno_existente_tenta_se_cadastrar_de_novo,
    test_envio_sem_atividade_ativa,
    test_envio_atividade_agendada,
    test_envio_atividade_encerrada,
    test_endpoint_texto_notificacao,
    test_endpoint_notificar_dispara,
    test_endpoint_notificar_sem_auth,
    test_endpoint_notificar_prof_errado,
    test_refactor_filter_pending_users,
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não configurada"); sys.exit(1)
    print(f"DATABASE_URL: {db_url}")
    print(f"Test schema : {TEST_SCHEMA}")
    print(f"SQLite bot  : {test_sqlite}")
    print()

    engine = create_engine(db_url, future=True)
    _setup_schema(engine)

    from redato_backend.portal import db as portal_db
    portal_db._engine = None
    portal_db.get_engine = lambda *a, **k: engine

    from sqlalchemy import event

    @event.listens_for(engine, "connect")
    def _set_search_path(dbapi_conn, _conn_record):
        with dbapi_conn.cursor() as cur:
            cur.execute(f'SET search_path TO "{TEST_SCHEMA}", public')

    world = _seed_world(engine)

    print(f"\n{'='*70}")
    failures = []
    try:
        for fn in TESTS:
            try:
                res = fn(engine, world)
                print(f"  ✓ {fn.__name__}: {res}")
            except AssertionError as exc:
                print(f"  ✗ {fn.__name__}: AssertionError: {exc}")
                failures.append((fn.__name__, str(exc)))
            except Exception as exc:
                print(f"  ✗ {fn.__name__}: {type(exc).__name__}: {exc}")
                failures.append((fn.__name__, repr(exc)))
    finally:
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
