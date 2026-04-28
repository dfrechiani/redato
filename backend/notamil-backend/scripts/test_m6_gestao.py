#!/usr/bin/env python3
"""Smoke M6 — endpoints de gestão (turmas, atividades, alunos, perfil).

Testa contratos HTTP dos endpoints novos do M6 contra Postgres em
schema isolado. Não toca front-end — exercita só a API.

Cenários:
- GET /portal/missoes retorna 5 missões REJ 1S
- GET /portal/turmas: prof vê só dele, coord vê escola inteira
- GET /portal/turmas/{id}: pode_criar_atividade reflete papel
- POST /portal/atividades: cria, valida datas, detecta duplicata
- POST /portal/atividades com confirmar_duplicata=True força criação
- POST /portal/atividades só pelo professor responsável (coord 403)
- GET /portal/atividades/{id}: status calculado, distribuição, top-detectores
- PATCH /portal/atividades/{id}: edita prazo
- POST /portal/atividades/{id}/encerrar: data_fim = now()
- GET /portal/atividades/{id}/envios/{aluno_id}: feedback completo
- PATCH /portal/turmas/{id}/alunos/{id}: marca inativo
- POST /auth/perfil/mudar-senha: troca senha (current sessão segue OK)
- POST /auth/perfil/mudar-senha: senha atual errada → 401
- POST /auth/perfil/sair-todas-sessoes: invalida tokens emitidos antes
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

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
    "test_secret_at_least_32_chars_for_smoke_m6_gestao_endpoints_xx",
)
os.environ.setdefault("ADMIN_TOKEN", "test-admin-token-m6")
os.environ.pop("SENDGRID_API_KEY", None)
os.environ.pop("TWILIO_ACCOUNT_SID", None)

TEST_SCHEMA = f"m6_test_{uuid.uuid4().hex[:8]}"
test_audit = Path(tempfile.mkdtemp(prefix="m6audit_")) / "audit_log.jsonl"

from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from redato_backend.portal.db import Base  # noqa: E402
from redato_backend.portal import models  # noqa: F401, E402
from redato_backend.portal import portal_api  # noqa: E402
from redato_backend.portal.auth.jwt_service import encode_token  # noqa: E402
from redato_backend.portal.auth.password import hash_senha  # noqa: E402
from redato_backend.portal.models import (  # noqa: E402
    AlunoTurma, Atividade, Coordenador, Envio, Escola, Interaction,
    Missao, Professor, Turma,
)
from redato_backend.portal.seed_missoes import seed_missoes  # noqa: E402


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
    def __init__(self):
        self.escola_a_id = None
        self.escola_b_id = None
        self.prof_a_id = None
        self.prof_b_id = None
        self.coord_a_id = None
        self.turma_a_id = None
        self.turma_b_id = None
        self.aluno_id = None
        self.aluno_inativar_id = None
        self.atividade_ativa_id = None
        self.missao_c3_id = None
        self.missao_c4_id = None


def _seed_world(engine) -> World:
    w = World()
    with Session(engine) as session:
        seed_missoes(session)
        session.commit()

        ea = Escola(codigo=f"E-CE-{uuid.uuid4().hex[:6]}", nome="Escola A",
                    estado="CE", municipio="Fortaleza")
        eb = Escola(codigo=f"E-CE-{uuid.uuid4().hex[:6]}", nome="Escola B",
                    estado="CE", municipio="Fortaleza")
        session.add_all([ea, eb]); session.flush()

        ca = Coordenador(escola_id=ea.id, nome="Coord A",
                         email=f"coord-a-{uuid.uuid4().hex[:4]}@e.br",
                         senha_hash=hash_senha("Senha123Forte"))
        pa = Professor(escola_id=ea.id, nome="Prof A",
                       email=f"prof-a-{uuid.uuid4().hex[:4]}@e.br",
                       senha_hash=hash_senha("Senha123Forte"))
        pb = Professor(escola_id=eb.id, nome="Prof B",
                       email=f"prof-b-{uuid.uuid4().hex[:4]}@e.br",
                       senha_hash=hash_senha("Senha123Forte"))
        session.add_all([ca, pa, pb]); session.flush()

        ta = Turma(escola_id=ea.id, professor_id=pa.id, codigo="1A",
                   serie="1S", codigo_join=f"TURMA-A-{uuid.uuid4().hex[:4]}-2026",
                   ano_letivo=2026)
        tb = Turma(escola_id=eb.id, professor_id=pb.id, codigo="1A",
                   serie="1S", codigo_join=f"TURMA-B-{uuid.uuid4().hex[:4]}-2026",
                   ano_letivo=2026)
        session.add_all([ta, tb]); session.flush()

        # Alunos
        a1 = AlunoTurma(turma_id=ta.id, nome="Maria Aluna",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a2 = AlunoTurma(turma_id=ta.id, nome="João Aluno",
                        telefone=f"+5511{uuid.uuid4().hex[:8]}")
        session.add_all([a1, a2]); session.flush()

        m_c3 = session.execute(
            select_codigo := text(
                f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                f"WHERE codigo = 'RJ1·OF10·MF'"
            )
        ).scalar()
        m_c4 = session.execute(
            text(f"SELECT id FROM \"{TEST_SCHEMA}\".missoes "
                 f"WHERE codigo = 'RJ1·OF11·MF'")
        ).scalar()

        agora = datetime.now(timezone.utc)
        atv = Atividade(
            turma_id=ta.id, missao_id=m_c3,
            data_inicio=agora - timedelta(hours=1),
            data_fim=agora + timedelta(days=7),
            criada_por_professor_id=pa.id,
        )
        session.add(atv); session.flush()

        # Cria 1 envio com nota completa pra exercitar agregados
        interaction = Interaction(
            aluno_phone=a1.telefone, aluno_turma_id=a1.id, envio_id=None,
            source="whatsapp_portal", missao_id="RJ1·OF10·MF",
            activity_id=str(uuid.uuid4()),
            redato_output=json.dumps({
                "nota_total": 720,
                "C1": {"nota": 160}, "C2": {"nota": 160},
                "C3": {"nota": 120}, "C4": {"nota": 160}, "C5": {"nota": 120},
                "audit_pedagogico": "Texto coeso, boa argumentação.",
                "flag_repeticao_lexical": True,
                "detector_falacia": False,
            }, ensure_ascii=False),
            ocr_quality_issues=json.dumps([]),
        )
        session.add(interaction); session.flush()
        envio = Envio(atividade_id=atv.id, aluno_turma_id=a1.id,
                      interaction_id=interaction.id, enviado_em=agora)
        session.add(envio); session.flush()
        interaction.envio_id = envio.id

        session.commit()

        w.escola_a_id = ea.id
        w.escola_b_id = eb.id
        w.coord_a_id = ca.id
        w.prof_a_id = pa.id
        w.prof_b_id = pb.id
        w.turma_a_id = ta.id
        w.turma_b_id = tb.id
        w.aluno_id = a1.id
        w.aluno_inativar_id = a2.id
        w.atividade_ativa_id = atv.id
        w.missao_c3_id = m_c3
        w.missao_c4_id = m_c4
    return w


def _client():
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app
    return TestClient(app)


def _bearer(world, papel: str) -> dict:
    if papel == "professor_a":
        token, _ = encode_token(
            user_id=str(world.prof_a_id), papel="professor",
            escola_id=str(world.escola_a_id),
        )
    elif papel == "professor_b":
        token, _ = encode_token(
            user_id=str(world.prof_b_id), papel="professor",
            escola_id=str(world.escola_b_id),
        )
    elif papel == "coord_a":
        token, _ = encode_token(
            user_id=str(world.coord_a_id), papel="coordenador",
            escola_id=str(world.escola_a_id),
        )
    else:
        raise ValueError(papel)
    return {"Authorization": f"Bearer {token}"}


# ──────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────

def test_missoes_lista(_engine, world):
    r = _client().get("/portal/missoes", headers=_bearer(world, "professor_a"))
    assert r.status_code == 200, r.text
    data = r.json()
    assert len(data) == 5
    codigos = {m["codigo"] for m in data}
    assert "RJ1·OF10·MF" in codigos
    return f"missoes: 5 itens REJ 1S ✓"


def test_turmas_professor_vs_coord(_engine, world):
    cli = _client()
    # Prof A vê só sua turma
    r1 = cli.get("/portal/turmas", headers=_bearer(world, "professor_a"))
    assert r1.status_code == 200
    ids_prof = {t["id"] for t in r1.json()}
    assert str(world.turma_a_id) in ids_prof
    assert str(world.turma_b_id) not in ids_prof

    # Coord A vê todas as turmas da escola A (apenas turma_a aqui)
    r2 = cli.get("/portal/turmas", headers=_bearer(world, "coord_a"))
    assert r2.status_code == 200
    ids_coord = {t["id"] for t in r2.json()}
    assert str(world.turma_a_id) in ids_coord
    assert str(world.turma_b_id) not in ids_coord
    return "GET /portal/turmas: prof vê só dele, coord vê escola ✓"


def test_turma_detail_pode_criar(_engine, world):
    cli = _client()
    r1 = cli.get(f"/portal/turmas/{world.turma_a_id}",
                 headers=_bearer(world, "professor_a"))
    assert r1.status_code == 200, r1.text
    body1 = r1.json()
    assert body1["pode_criar_atividade"] is True
    assert len(body1["alunos"]) == 2

    r2 = cli.get(f"/portal/turmas/{world.turma_a_id}",
                 headers=_bearer(world, "coord_a"))
    assert r2.status_code == 200
    assert r2.json()["pode_criar_atividade"] is False

    # prof B (outra escola) → 403
    r3 = cli.get(f"/portal/turmas/{world.turma_a_id}",
                 headers=_bearer(world, "professor_b"))
    assert r3.status_code == 403
    return "GET /turmas/{id}: pode_criar_atividade ✓ + 403 prof errado ✓"


def test_criar_atividade_e_duplicata(_engine, world):
    cli = _client()
    agora = datetime.now(timezone.utc)
    body = {
        "turma_id": str(world.turma_a_id),
        "missao_id": str(world.missao_c4_id),
        "data_inicio": agora.isoformat(),
        "data_fim": (agora + timedelta(days=3)).isoformat(),
        "notificar_alunos": False,
    }
    r1 = cli.post("/portal/atividades", json=body,
                  headers=_bearer(world, "professor_a"))
    assert r1.status_code == 200, r1.text
    j1 = r1.json()
    assert j1["id"] is not None
    assert j1["duplicate_warning"] is False

    # Mesmo body → duplicate_warning=True, sem criar
    r2 = cli.post("/portal/atividades", json=body,
                  headers=_bearer(world, "professor_a"))
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["duplicate_warning"] is True
    assert j2["id"] is None
    assert j2["duplicata_atividade_id"] == j1["id"]

    # Confirma duplicata → cria
    body["confirmar_duplicata"] = True
    r3 = cli.post("/portal/atividades", json=body,
                  headers=_bearer(world, "professor_a"))
    assert r3.status_code == 200
    j3 = r3.json()
    assert j3["id"] is not None
    assert j3["id"] != j1["id"]
    return "POST /atividades: cria + detecta duplicata + confirma ✓"


def test_criar_atividade_coord_403(_engine, world):
    cli = _client()
    agora = datetime.now(timezone.utc)
    body = {
        "turma_id": str(world.turma_a_id),
        "missao_id": str(world.missao_c4_id),
        "data_inicio": agora.isoformat(),
        "data_fim": (agora + timedelta(days=2)).isoformat(),
    }
    r = cli.post("/portal/atividades", json=body,
                 headers=_bearer(world, "coord_a"))
    assert r.status_code == 403, r.text
    return "POST /atividades: coord 403 ✓"


def test_criar_atividade_datas_invalidas(_engine, world):
    cli = _client()
    agora = datetime.now(timezone.utc)
    body = {
        "turma_id": str(world.turma_a_id),
        "missao_id": str(world.missao_c4_id),
        "data_inicio": (agora + timedelta(days=2)).isoformat(),
        "data_fim": agora.isoformat(),  # invertido
    }
    r = cli.post("/portal/atividades", json=body,
                 headers=_bearer(world, "professor_a"))
    assert r.status_code == 400
    return "POST /atividades: data_fim <= data_inicio → 400 ✓"


def test_detalhe_atividade_agregados(_engine, world):
    cli = _client()
    r = cli.get(f"/portal/atividades/{world.atividade_ativa_id}",
                headers=_bearer(world, "professor_a"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ativa"
    assert body["n_alunos_total"] == 2
    assert body["n_enviados"] == 1
    assert body["n_pendentes"] == 1
    assert body["distribuicao"]["601-800"] == 1
    # Detector com flag_ True
    # M7: top_detectores agora usa codigo canônico normalizado
    # ("repeticao_lexical" sem prefixo flag_).
    detectores_codigos = {d["codigo"] for d in body["top_detectores"]}
    assert "repeticao_lexical" in detectores_codigos
    # Lista de envios contém ambos os alunos (1 com nota, 1 pendente)
    assert len(body["envios"]) == 2
    enviados = [e for e in body["envios"] if e["enviado_em"]]
    pendentes = [e for e in body["envios"] if not e["enviado_em"]]
    assert len(enviados) == 1 and enviados[0]["nota_total"] == 720
    assert len(pendentes) == 1
    return f"GET /atividades/{{id}}: agregados+envios ✓"


def test_patch_atividade_prazo(_engine, world):
    cli = _client()
    novo_fim = datetime.now(timezone.utc) + timedelta(days=14)
    r = cli.patch(
        f"/portal/atividades/{world.atividade_ativa_id}",
        json={"data_fim": novo_fim.isoformat()},
        headers=_bearer(world, "professor_a"),
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert "data_fim" in j
    return "PATCH /atividades/{id}: edita data_fim ✓"


def test_encerrar_atividade(_engine, world):
    cli = _client()
    r = cli.post(
        f"/portal/atividades/{world.atividade_ativa_id}/encerrar",
        headers=_bearer(world, "professor_a"),
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "encerrada"
    return "POST /atividades/{id}/encerrar: encerrou ✓"


def test_envio_feedback_aluno(_engine, world):
    cli = _client()
    r = cli.get(
        f"/portal/atividades/{world.atividade_ativa_id}/envios/{world.aluno_id}",
        headers=_bearer(world, "professor_a"),
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["nota_total"] == 720
    assert j["audit_pedagogico"] == "Texto coeso, boa argumentação."
    assert len(j["faixas"]) == 5
    return f"GET /atividades/{{id}}/envios/{{aluno}}: feedback completo ✓"


def test_envio_feedback_aluno_sem_envio(_engine, world):
    cli = _client()
    r = cli.get(
        f"/portal/atividades/{world.atividade_ativa_id}/envios/"
        f"{world.aluno_inativar_id}",
        headers=_bearer(world, "professor_a"),
    )
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["enviado_em"] is None
    assert j["nota_total"] is None
    return "GET /envio: aluno sem envio retorna 200 com nota=null ✓"


def test_inativar_aluno(_engine, world):
    cli = _client()
    r = cli.patch(
        f"/portal/turmas/{world.turma_a_id}/alunos/{world.aluno_inativar_id}",
        json={"ativo": False},
        headers=_bearer(world, "professor_a"),
    )
    assert r.status_code == 200
    assert r.json()["ativo"] is False
    # Coord não pode (mesmo da escola dele)
    r2 = cli.patch(
        f"/portal/turmas/{world.turma_a_id}/alunos/{world.aluno_inativar_id}",
        json={"ativo": True},
        headers=_bearer(world, "coord_a"),
    )
    assert r2.status_code == 403
    return "PATCH alunos/{id}: prof inativa ✓ + coord 403 ✓"


def test_perfil_mudar_senha(_engine, world):
    cli = _client()
    # Senha errada → 401
    r1 = cli.post(
        "/auth/perfil/mudar-senha",
        json={"senha_atual": "errada123", "senha_nova": "NovaForte123"},
        headers=_bearer(world, "professor_a"),
    )
    assert r1.status_code == 401, r1.text

    # Senha correta → 200
    r2 = cli.post(
        "/auth/perfil/mudar-senha",
        json={"senha_atual": "Senha123Forte", "senha_nova": "OutraForte456"},
        headers=_bearer(world, "professor_a"),
    )
    assert r2.status_code == 200, r2.text

    # Senha fraca → 400
    r3 = cli.post(
        "/auth/perfil/mudar-senha",
        json={"senha_atual": "OutraForte456", "senha_nova": "abc"},
        headers=_bearer(world, "professor_a"),
    )
    assert r3.status_code == 400
    return "POST /perfil/mudar-senha: senha errada 401, OK 200, fraca 400 ✓"


def test_sair_todas_sessoes(_engine, world):
    cli = _client()
    # Cria sessão antiga (token T1) — pra coord_a
    headers = _bearer(world, "coord_a")
    r1 = cli.get("/auth/me", headers=headers)
    assert r1.status_code == 200

    # Espera 1s pra que iat de T2 > sessoes_invalidadas_em > iat de T1
    time.sleep(1.1)

    # Sair de todas as sessões — invalida T1
    r2 = cli.post("/auth/perfil/sair-todas-sessoes", headers=headers)
    assert r2.status_code == 200, r2.text

    # Token antigo agora deve dar 401
    r3 = cli.get("/auth/me", headers=headers)
    assert r3.status_code == 401, f"esperava 401, got {r3.status_code}"

    # Mas um novo token (issued após o cut) é aceito
    time.sleep(1.1)
    headers_novo = _bearer(world, "coord_a")
    r4 = cli.get("/auth/me", headers=headers_novo)
    assert r4.status_code == 200
    return "POST /perfil/sair-todas-sessoes: invalida tokens antigos ✓"


# ──────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────

TESTS = [
    test_missoes_lista,
    test_turmas_professor_vs_coord,
    test_turma_detail_pode_criar,
    test_criar_atividade_e_duplicata,
    test_criar_atividade_coord_403,
    test_criar_atividade_datas_invalidas,
    test_detalhe_atividade_agregados,
    test_patch_atividade_prazo,
    test_encerrar_atividade,
    test_envio_feedback_aluno,
    test_envio_feedback_aluno_sem_envio,
    test_inativar_aluno,
    test_perfil_mudar_senha,
    test_sair_todas_sessoes,
]


def main():
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERRO: DATABASE_URL não configurada")
        sys.exit(1)
    print(f"DATABASE_URL: {db_url}")
    print(f"Test schema : {TEST_SCHEMA}\n")

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

    print(f"{'='*70}")
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
                import traceback
                traceback.print_exc()
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
