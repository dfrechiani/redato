"""Testes E2E dos endpoints REST de partidas (Fase 2 passo 3).

Testes integração via FastAPI TestClient + Postgres real (schema
isolado por run). Skip automático se DATABASE_URL não estiver
definido — `pytest` local sem Postgres pula esse arquivo inteiro.

Padrão segue `scripts/test_m6_gestao.py` mas em forma pytest pra
integrar com a suite. Cada teste recebe `client` (TestClient) +
`world` (objeto com IDs das fixtures) + `bearer` (factory de auth
header).

Cobre:
- POST partidas: feliz, atividade de outra turma, tema invalid,
  grupo duplicado, prazo passado, aluno fora da turma, prazo naive
- GET partidas/{id}: como professor da turma, professor de outra
  turma (403), inexistente (404)
- GET atividades/{id}/partidas: lista ordenada, vazia
- GET jogos/minidecks: 7 ativos
- PATCH: atualiza grupo_codigo, prazo; rejeita atividade_id
- DELETE: sem reescritas (200), com reescritas (409)
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import pytest


# ──────────────────────────────────────────────────────────────────────
# Skip global se sem Postgres
# ──────────────────────────────────────────────────────────────────────

pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason=(
        "DATABASE_URL não definido — testes de endpoint exigem "
        "Postgres real (ARRAY/JSONB + JWT auth via DB). Rode com "
        "DATABASE_URL=postgresql://... pytest"
    ),
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures — schema isolado + world seed
# ──────────────────────────────────────────────────────────────────────

class _World:
    """Container de IDs das fixtures do test. Atributos preenchidos
    em `world` fixture."""
    test_schema: str
    escola_id: uuid.UUID
    professor_id: uuid.UUID
    professor_outro_id: uuid.UUID
    professor_outro_escola_id: uuid.UUID
    coordenador_id: uuid.UUID
    turma_id: uuid.UUID
    turma_outra_id: uuid.UUID
    aluno_a_id: uuid.UUID
    aluno_b_id: uuid.UUID
    aluno_c_id: uuid.UUID
    aluno_outra_turma_id: uuid.UUID
    missao_id: uuid.UUID
    atividade_id: uuid.UUID
    minideck_saude_mental_id: uuid.UUID
    minideck_inativo_id: uuid.UUID


@pytest.fixture(scope="module")
def engine_e_schema():
    """Cria schema isolado, aplica metadata, retorna (engine,
    test_schema). Teardown: DROP SCHEMA CASCADE no final do módulo."""
    from sqlalchemy import create_engine, text

    from redato_backend.portal.db import Base
    from redato_backend.portal import models  # noqa: F401

    test_schema = f"jogo_api_test_{uuid.uuid4().hex[:8]}"
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"options": f"-csearch_path={test_schema}"},
    )
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()
    # search_path no connect_args + NÃO muta Base.metadata.tables[*]
    # .schema (evita leak entre módulos no full pytest run).
    Base.metadata.create_all(engine)

    yield engine, test_schema

    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
        conn.commit()


@pytest.fixture(scope="module")
def world(engine_e_schema) -> _World:
    """Seed do "mundo" mínimo pros tests: 1 escola, 2 professores
    (1 da escola, 1 de outra escola), 1 coordenador, 2 turmas
    (1 do prof A, 1 do prof B), 4 alunos (3 na turma A, 1 na turma
    B), 1 atividade da turma A, 2 minidecks (saude_mental ativo,
    inativo)."""
    from sqlalchemy.orm import Session

    from redato_backend.portal.auth.password import hash_senha
    from redato_backend.portal.models import (
        AlunoTurma, Atividade, Coordenador, Escola, JogoMinideck,
        Missao, Professor, Turma,
    )

    engine, test_schema = engine_e_schema
    w = _World()
    w.test_schema = test_schema

    with Session(engine) as session:
        escola = Escola(
            codigo=f"E-{uuid.uuid4().hex[:6]}", nome="Escola A",
            estado="SP", municipio="São Paulo",
        )
        escola_outra = Escola(
            codigo=f"E-{uuid.uuid4().hex[:6]}", nome="Escola B",
            estado="SP", municipio="São Paulo",
        )
        session.add_all([escola, escola_outra])
        session.flush()
        w.escola_id = escola.id
        w.professor_outro_escola_id = escola_outra.id

        prof = Professor(
            escola_id=escola.id, nome="Prof A",
            email=f"profa-{uuid.uuid4().hex[:6]}@e.br",
            senha_hash=hash_senha("Senha123Forte"),
        )
        prof_outro = Professor(
            escola_id=escola_outra.id, nome="Prof B",
            email=f"profb-{uuid.uuid4().hex[:6]}@e.br",
            senha_hash=hash_senha("Senha123Forte"),
        )
        coord = Coordenador(
            escola_id=escola.id, nome="Coord",
            email=f"coord-{uuid.uuid4().hex[:6]}@e.br",
            senha_hash=hash_senha("Senha123Forte"),
        )
        session.add_all([prof, prof_outro, coord])
        session.flush()
        w.professor_id = prof.id
        w.professor_outro_id = prof_outro.id
        w.coordenador_id = coord.id

        turma = Turma(
            escola_id=escola.id, professor_id=prof.id,
            codigo="2A", serie="2S",
            codigo_join=f"TURMA-A-{uuid.uuid4().hex[:4]}",
            ano_letivo=2026,
        )
        turma_outra = Turma(
            escola_id=escola_outra.id, professor_id=prof_outro.id,
            codigo="2B", serie="2S",
            codigo_join=f"TURMA-B-{uuid.uuid4().hex[:4]}",
            ano_letivo=2026,
        )
        session.add_all([turma, turma_outra])
        session.flush()
        w.turma_id = turma.id
        w.turma_outra_id = turma_outra.id

        a, b, c = (
            AlunoTurma(turma_id=turma.id, nome="Maria",
                       telefone=f"+55{uuid.uuid4().hex[:9]}"),
            AlunoTurma(turma_id=turma.id, nome="João",
                       telefone=f"+55{uuid.uuid4().hex[:9]}"),
            AlunoTurma(turma_id=turma.id, nome="Ana",
                       telefone=f"+55{uuid.uuid4().hex[:9]}"),
        )
        d = AlunoTurma(turma_id=turma_outra.id, nome="Pedro",
                       telefone=f"+55{uuid.uuid4().hex[:9]}")
        session.add_all([a, b, c, d])
        session.flush()
        w.aluno_a_id = a.id
        w.aluno_b_id = b.id
        w.aluno_c_id = c.id
        w.aluno_outra_turma_id = d.id

        missao = Missao(
            codigo=f"RJ2·OF13·MF·{uuid.uuid4().hex[:4]}",
            serie="2S", oficina_numero=13,
            titulo="Jogo Completo (test)",
            modo_correcao="completo",
        )
        session.add(missao); session.flush()
        w.missao_id = missao.id

        agora = datetime.now(timezone.utc)
        ativ = Atividade(
            turma_id=turma.id, missao_id=missao.id,
            data_inicio=agora - timedelta(hours=1),
            data_fim=agora + timedelta(days=14),
            criada_por_professor_id=prof.id,
        )
        session.add(ativ); session.flush()
        w.atividade_id = ativ.id

        md = JogoMinideck(
            tema="saude_mental",
            nome_humano="Saúde Mental",
            serie="2S", ativo=True,
        )
        md_inativo = JogoMinideck(
            tema=f"tema_inativo_{uuid.uuid4().hex[:6]}",
            nome_humano="Tema Inativo",
            serie="2S", ativo=False,
        )
        session.add_all([md, md_inativo])
        session.flush()
        w.minideck_saude_mental_id = md.id
        w.minideck_inativo_id = md_inativo.id

        session.commit()

    return w


@pytest.fixture(scope="module")
def client(engine_e_schema):
    """TestClient apontado pro app. Injeta engine isolado em
    `portal.db._engine` (cache global). Não monkey-patcha `get_engine`
    porque módulos importam `get_engine` por nome — bindings locais
    não são afetados. Trocar o cache funciona porque a função original
    consulta o cache antes de criar nova engine."""
    from fastapi.testclient import TestClient

    from redato_backend.portal.portal_app import app

    engine, _ = engine_e_schema
    import redato_backend.portal.db as dbmod
    original_engine = dbmod._engine
    dbmod._engine = engine

    yield TestClient(app)

    dbmod._engine = original_engine


@pytest.fixture
def bearer(world):
    """Factory que retorna {Authorization: Bearer ...} pra cada
    user."""
    from redato_backend.portal.auth.jwt_service import encode_token

    def _make(papel: str) -> Dict[str, str]:
        if papel == "professor":
            uid, esc = world.professor_id, world.escola_id
            p = "professor"
        elif papel == "professor_outro":
            uid = world.professor_outro_id
            esc = world.professor_outro_escola_id
            p = "professor"
        elif papel == "coordenador":
            uid, esc = world.coordenador_id, world.escola_id
            p = "coordenador"
        else:
            raise ValueError(papel)
        token, _ = encode_token(
            user_id=str(uid), papel=p, escola_id=str(esc),
        )
        return {"Authorization": f"Bearer {token}"}

    return _make


# ──────────────────────────────────────────────────────────────────────
# Helper — body padrão de POST /partidas
# ──────────────────────────────────────────────────────────────────────

def _body_partida(
    world: _World, *,
    grupo_codigo: str = "Grupo Azul",
    alunos: List[uuid.UUID] | None = None,
    prazo: datetime | None = None,
    tema: str = "saude_mental",
    atividade_id: uuid.UUID | None = None,
) -> Dict[str, Any]:
    if alunos is None:
        alunos = [world.aluno_a_id, world.aluno_b_id]
    if prazo is None:
        prazo = datetime.now(timezone.utc) + timedelta(days=7)
    return {
        "atividade_id": str(atividade_id or world.atividade_id),
        "tema": tema,
        "grupo_codigo": grupo_codigo,
        "alunos_turma_ids": [str(a) for a in alunos],
        "prazo_reescrita": prazo.isoformat(),
    }


# ──────────────────────────────────────────────────────────────────────
# POST /portal/partidas
# ──────────────────────────────────────────────────────────────────────

def test_post_partida_caso_feliz(client, world, bearer):
    body = _body_partida(world, grupo_codigo="Grupo Feliz 1")
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert "id" in data
    assert data["partida"]["grupo_codigo"] == "Grupo Feliz 1"
    assert data["partida"]["tema"] == "saude_mental"
    assert data["partida"]["nome_humano_tema"] == "Saúde Mental"
    assert len(data["partida"]["alunos"]) == 2
    assert data["partida"]["status_partida"] == "aguardando_cartas"


def test_post_partida_outro_professor_403(client, world, bearer):
    body = _body_partida(world, grupo_codigo="Grupo X")
    r = client.post(
        "/portal/partidas", json=body,
        headers=bearer("professor_outro"),
    )
    assert r.status_code == 403, r.text
    assert "professor responsável" in r.json()["detail"]


def test_post_partida_tema_invalido_400(client, world, bearer):
    body = _body_partida(
        world, grupo_codigo="Grupo Y", tema="tema_que_nao_existe",
    )
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    assert r.status_code == 400
    assert "minideck ativo" in r.json()["detail"]


def test_post_partida_minideck_inativo_400(client, world, bearer):
    """Tema existe em jogos_minideck mas ativo=False → mesma resposta
    que tema inexistente."""
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import JogoMinideck
    with Session(get_engine()) as s:
        md = s.get(JogoMinideck, world.minideck_inativo_id)
        body = _body_partida(world, grupo_codigo="Grupo Z", tema=md.tema)
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    assert r.status_code == 400


def test_post_partida_grupo_duplicado_409(client, world, bearer):
    body1 = _body_partida(world, grupo_codigo="Grupo Dup")
    r1 = client.post(
        "/portal/partidas", json=body1, headers=bearer("professor"),
    )
    assert r1.status_code == 201
    r2 = client.post(
        "/portal/partidas", json=body1, headers=bearer("professor"),
    )
    assert r2.status_code == 409, r2.text
    assert "Já existe" in r2.json()["detail"]


def test_post_partida_prazo_passado_400(client, world, bearer):
    prazo = datetime.now(timezone.utc) - timedelta(hours=1)
    body = _body_partida(
        world, grupo_codigo="Grupo Passado", prazo=prazo,
    )
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    assert r.status_code == 400
    assert "futuro" in r.json()["detail"]


def test_post_partida_prazo_naive_400(client, world, bearer):
    """ISO sem timezone offset — recusado pra evitar ambiguidade."""
    body = _body_partida(world, grupo_codigo="Grupo Naive")
    body["prazo_reescrita"] = "2027-01-01T10:00:00"  # sem offset
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    assert r.status_code == 400
    assert "timezone" in r.json()["detail"].lower() or \
        "tz" in r.json()["detail"].lower() or \
        "aware" in r.json()["detail"].lower()


def test_post_partida_aluno_de_outra_turma_400(client, world, bearer):
    body = _body_partida(
        world, grupo_codigo="Grupo Misto",
        alunos=[world.aluno_a_id, world.aluno_outra_turma_id],
    )
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    assert r.status_code == 400
    assert "turma diferente" in r.json()["detail"]


def test_post_partida_aluno_inexistente_400(client, world, bearer):
    body = _body_partida(
        world, grupo_codigo="Grupo Fantasma",
        alunos=[world.aluno_a_id, uuid.uuid4()],
    )
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    assert r.status_code == 400
    assert "não encontrados" in r.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# GET /portal/partidas/{id}
# ──────────────────────────────────────────────────────────────────────

def test_get_partida_como_professor_da_turma(client, world, bearer):
    body = _body_partida(world, grupo_codigo="Grupo GET 1")
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    pid = r.json()["id"]

    r2 = client.get(
        f"/portal/partidas/{pid}", headers=bearer("professor"),
    )
    assert r2.status_code == 200
    assert r2.json()["grupo_codigo"] == "Grupo GET 1"
    assert isinstance(r2.json()["reescritas"], list)
    assert r2.json()["reescritas"] == []


def test_get_partida_outro_professor_403(client, world, bearer):
    body = _body_partida(world, grupo_codigo="Grupo GET 2")
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    pid = r.json()["id"]

    r2 = client.get(
        f"/portal/partidas/{pid}",
        headers=bearer("professor_outro"),
    )
    assert r2.status_code == 403


def test_get_partida_inexistente_404(client, bearer):
    r = client.get(
        f"/portal/partidas/{uuid.uuid4()}",
        headers=bearer("professor"),
    )
    assert r.status_code == 404


# ──────────────────────────────────────────────────────────────────────
# GET /portal/atividades/{id}/partidas
# ──────────────────────────────────────────────────────────────────────

def test_get_lista_partidas_da_atividade(client, world, bearer):
    # Cria 2 partidas distintas (grupos diferentes)
    for i in range(2):
        body = _body_partida(world, grupo_codigo=f"Grupo Lista {i}")
        client.post(
            "/portal/partidas", json=body,
            headers=bearer("professor"),
        )

    r = client.get(
        f"/portal/atividades/{world.atividade_id}/partidas",
        headers=bearer("professor"),
    )
    assert r.status_code == 200
    items = r.json()
    grupos = [p["grupo_codigo"] for p in items]
    assert "Grupo Lista 0" in grupos
    assert "Grupo Lista 1" in grupos
    # Ordenado asc por created_at
    assert grupos.index("Grupo Lista 0") < grupos.index("Grupo Lista 1")


def test_get_lista_partidas_outro_professor_403(client, world, bearer):
    r = client.get(
        f"/portal/atividades/{world.atividade_id}/partidas",
        headers=bearer("professor_outro"),
    )
    assert r.status_code == 403


# ──────────────────────────────────────────────────────────────────────
# GET /portal/jogos/minidecks
# ──────────────────────────────────────────────────────────────────────

def test_get_minidecks_lista_apenas_ativos(client, world, bearer):
    r = client.get(
        "/portal/jogos/minidecks", headers=bearer("professor"),
    )
    assert r.status_code == 200
    temas = [m["tema"] for m in r.json()]
    assert "saude_mental" in temas
    # Inativo não aparece
    for m in r.json():
        assert "inativo" not in m["tema"]


# ──────────────────────────────────────────────────────────────────────
# PATCH /portal/partidas/{id}
# ──────────────────────────────────────────────────────────────────────

def test_patch_grupo_codigo(client, world, bearer):
    body = _body_partida(world, grupo_codigo="Grupo Patch 1")
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    pid = r.json()["id"]

    r2 = client.patch(
        f"/portal/partidas/{pid}",
        json={"grupo_codigo": "Grupo Patch 1 RENOMEADO"},
        headers=bearer("professor"),
    )
    assert r2.status_code == 200
    assert r2.json()["grupo_codigo"] == "Grupo Patch 1 RENOMEADO"


def test_patch_atividade_id_ignorado_silenciosamente(client, world, bearer):
    """PartidaUpdate não tem `atividade_id` — Pydantic descarta. PATCH
    com esse campo no body não muda nada (é estrita por config; aqui
    a Pydantic v2 default é ignore extras → o campo não chega no
    handler). Comportamento esperado: 200 sem alteração."""
    body = _body_partida(world, grupo_codigo="Grupo Imutavel")
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    pid = r.json()["id"]
    aid_original = r.json()["partida"]["atividade_id"]

    r2 = client.patch(
        f"/portal/partidas/{pid}",
        json={"atividade_id": str(uuid.uuid4())},
        headers=bearer("professor"),
    )
    assert r2.status_code == 200
    assert r2.json()["atividade_id"] == aid_original


def test_patch_grupo_duplicado_409(client, world, bearer):
    body1 = _body_partida(world, grupo_codigo="Grupo Patch A")
    body2 = _body_partida(world, grupo_codigo="Grupo Patch B")
    client.post("/portal/partidas", json=body1,
                headers=bearer("professor"))
    r2 = client.post("/portal/partidas", json=body2,
                      headers=bearer("professor"))
    pid_b = r2.json()["id"]

    # Tenta renomear B pro nome de A → conflito
    r3 = client.patch(
        f"/portal/partidas/{pid_b}",
        json={"grupo_codigo": "Grupo Patch A"},
        headers=bearer("professor"),
    )
    assert r3.status_code == 409


# ──────────────────────────────────────────────────────────────────────
# DELETE /portal/partidas/{id}
# ──────────────────────────────────────────────────────────────────────

def test_delete_partida_sem_reescritas_200(client, world, bearer):
    body = _body_partida(world, grupo_codigo="Grupo Delete 1")
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    pid = r.json()["id"]

    r2 = client.delete(
        f"/portal/partidas/{pid}", headers=bearer("professor"),
    )
    assert r2.status_code == 200
    assert r2.json()["deleted_id"] == pid

    # Verifica que sumiu
    r3 = client.get(
        f"/portal/partidas/{pid}", headers=bearer("professor"),
    )
    assert r3.status_code == 404


def test_delete_partida_com_reescrita_409(client, world, bearer):
    """DELETE deve falhar 409 protegendo trabalho do aluno se a
    partida já tem reescrita criada."""
    from sqlalchemy.orm import Session

    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import ReescritaIndividual

    body = _body_partida(world, grupo_codigo="Grupo Delete 2")
    r = client.post(
        "/portal/partidas", json=body, headers=bearer("professor"),
    )
    pid = r.json()["id"]

    # Insere reescrita direto via SQL (no Fase 2 não tem endpoint
    # ainda).
    with Session(get_engine()) as s:
        rs = ReescritaIndividual(
            partida_id=uuid.UUID(pid),
            aluno_turma_id=world.aluno_a_id,
            texto="Reescrita de teste",
        )
        s.add(rs)
        s.commit()

    r2 = client.delete(
        f"/portal/partidas/{pid}", headers=bearer("professor"),
    )
    assert r2.status_code == 409
    assert "reescrita" in r2.json()["detail"].lower()
