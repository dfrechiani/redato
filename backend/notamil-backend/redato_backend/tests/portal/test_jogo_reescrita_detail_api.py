"""Testes E2E do endpoint GET /portal/partidas/{id}/reescritas/{aluno_id}
(Fase 2 passo 6 — UI do professor pra reescritas).

Postgres real obrigatório. Skip automático se DATABASE_URL ausente.
Padrão segue test_jogo_partidas_api.py.

Cobre 9 cenários:
- 200 com avaliação completa (redato_output preenchido)
- 200 com redato_output=null (Claude falhou no bot — caso real)
- 200 com flag DH=true (UI vai mostrar banner vermelho)
- 200 inclui cartas escolhidas com secao/cor pra estruturais e
  conteudo pra lacunas
- 403 quando professor de outra turma
- 404 quando partida não existe
- 404 quando aluno não pertence à partida
- 404 quando reescrita não existe (aluno ainda não respondeu)
- AlunoResumo em PartidaResumo agora tem reescrita_status
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL não definido — exige Postgres real",
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine_e_schema():
    from sqlalchemy import create_engine, text
    from redato_backend.portal.db import Base
    from redato_backend.portal import models  # noqa: F401

    test_schema = f"jogo_reescrita_test_{uuid.uuid4().hex[:8]}"
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"options": f"-csearch_path={test_schema}"},
    )
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()
    Base.metadata.create_all(engine)
    yield engine, test_schema
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
        conn.commit()


@pytest.fixture(scope="module")
def world(engine_e_schema):
    """Seed: 1 escola, 2 professores (1 dono da turma, 1 outra escola),
    1 turma, 3 alunos (a1, a2, a3 — a1 com reescrita avaliada, a2 com
    reescrita sem redato_output, a3 sem reescrita), 1 atividade,
    catálogo + minideck + 1 partida com a1+a2+a3."""
    from sqlalchemy.orm import Session
    from redato_backend.portal.auth.password import hash_senha
    from redato_backend.portal.models import (
        AlunoTurma, Atividade, CartaEstrutural, CartaLacuna, Escola,
        JogoMinideck, Missao, PartidaJogo, Professor,
        ReescritaIndividual, Turma,
    )

    engine, _ = engine_e_schema

    with Session(engine) as s:
        e = Escola(codigo=f"E-{uuid.uuid4().hex[:6]}", nome="Esc",
                    estado="SP", municipio="SP")
        e_outra = Escola(codigo=f"EX-{uuid.uuid4().hex[:6]}",
                          nome="Outra", estado="SP", municipio="SP")
        s.add_all([e, e_outra]); s.flush()
        prof = Professor(escola_id=e.id, nome="ProfDono",
                          email=f"p-{uuid.uuid4().hex[:6]}@x",
                          senha_hash=hash_senha("Senha123Forte"))
        prof_outro = Professor(escola_id=e_outra.id,
                                nome="ProfOutro",
                                email=f"o-{uuid.uuid4().hex[:6]}@x",
                                senha_hash=hash_senha("Senha123Forte"))
        s.add_all([prof, prof_outro]); s.flush()
        t = Turma(escola_id=e.id, professor_id=prof.id, codigo="2A",
                   serie="2S",
                   codigo_join=f"TURMA-{uuid.uuid4().hex[:6]}",
                   ano_letivo=2026)
        s.add(t); s.flush()
        a1 = AlunoTurma(turma_id=t.id, nome="Aluna A",
                         telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a2 = AlunoTurma(turma_id=t.id, nome="Aluno B",
                         telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a3 = AlunoTurma(turma_id=t.id, nome="Aluno C",
                         telefone=f"+5511{uuid.uuid4().hex[:8]}")
        s.add_all([a1, a2, a3]); s.flush()
        m = Missao(codigo=f"RJ2-{uuid.uuid4().hex[:6]}", serie="2S",
                    oficina_numero=13, titulo="Jogo Completo",
                    modo_correcao="completo")
        s.add(m); s.flush()
        agora = datetime.now(timezone.utc)
        ativ = Atividade(
            turma_id=t.id, missao_id=m.id,
            data_inicio=agora - timedelta(hours=1),
            data_fim=agora + timedelta(days=14),
            criada_por_professor_id=prof.id,
        )
        s.add(ativ); s.flush()

        # Catálogo mínimo: 2 estruturais + 2 lacunas
        s.add_all([
            CartaEstrutural(
                codigo="E01", secao="ABERTURA", cor="AZUL",
                texto="Texto E01 com [PROBLEMA].",
                lacunas=["PROBLEMA"], ordem=1,
            ),
            CartaEstrutural(
                codigo="E10", secao="TESE", cor="AZUL",
                texto="Texto E10 sem placeholder.",
                lacunas=[], ordem=2,
            ),
        ])
        s.flush()
        md = JogoMinideck(
            tema="saude_mental", nome_humano="Saúde Mental",
            serie="2S", ativo=True,
        )
        s.add(md); s.flush()
        s.add_all([
            CartaLacuna(minideck_id=md.id, tipo="PROBLEMA",
                         codigo="P01", conteudo="estigma social"),
            CartaLacuna(minideck_id=md.id, tipo="REPERTORIO",
                         codigo="R01", conteudo="OMS"),
        ])
        s.flush()

        partida = PartidaJogo(
            atividade_id=ativ.id, minideck_id=md.id,
            grupo_codigo="Grupo Teste",
            cartas_escolhidas={
                "_alunos_turma_ids": [
                    str(a1.id), str(a2.id), str(a3.id),
                ],
                "codigos": ["E01", "E10", "P01", "R01"],
            },
            texto_montado="Texto montado de exemplo do grupo.",
            prazo_reescrita=agora + timedelta(days=7),
            criada_por_professor_id=prof.id,
        )
        s.add(partida); s.flush()

        # Reescritas:
        # a1 — completa, com redato_output preenchido (avaliada)
        # a2 — sem redato_output (em_avaliacao)
        # a3 — sem reescrita (pendente)
        redato_output_a1: Dict[str, Any] = {
            "modo": "jogo_redacao",
            "tema_minideck": "saude_mental",
            "notas_enem": {"c1": 200, "c2": 200, "c3": 160,
                            "c4": 160, "c5": 160},
            "nota_total_enem": 880,
            "transformacao_cartas": 80,
            "sugestoes_cartas_alternativas": [
                {
                    "codigo_original": "P01",
                    "codigo_sugerido": "P05",
                    "motivo": "P05 dá mais especificidade.",
                },
            ],
            "flags": {
                "copia_literal_das_cartas": False,
                "cartas_mal_articuladas": False,
                "fuga_do_tema_do_minideck": False,
                "tipo_textual_inadequado": False,
                "desrespeito_direitos_humanos": False,
            },
            "feedback_aluno": {
                "acertos": ["Sua frase de abertura ficou clara."],
                "ajustes": ["Reforça o repertório com dado verificável."],
            },
            "feedback_professor": {
                "pontos_fortes": ["Recorte temático preservado."],
                "pontos_fracos": ["Repertório curto."],
                "padrao_falha": "repertório de bolso parcial",
                "transferencia_competencia": "treinar uso de dados",
            },
            "_mission": {"mode": "jogo_redacao"},
        }
        s.add(ReescritaIndividual(
            partida_id=partida.id, aluno_turma_id=a1.id,
            texto="Reescrita completa do aluno A com 100+ chars.",
            redato_output=redato_output_a1,
            elapsed_ms=12340,
        ))
        s.add(ReescritaIndividual(
            partida_id=partida.id, aluno_turma_id=a2.id,
            texto="Reescrita do aluno B sem avaliação Redato.",
            redato_output=None,
        ))
        # a3 — sem reescrita
        s.flush()
        s.commit()

        return {
            "engine": engine,
            "escola_id": e.id,
            "escola_outra_id": e_outra.id,
            "professor_id": prof.id,
            "professor_outro_id": prof_outro.id,
            "turma_id": t.id,
            "aluno_a1_id": a1.id,    # avaliada
            "aluno_a2_id": a2.id,    # em_avaliacao
            "aluno_a3_id": a3.id,    # pendente
            "ativ_id": ativ.id,
            "partida_id": partida.id,
        }


@pytest.fixture(scope="module")
def client(engine_e_schema):
    from fastapi.testclient import TestClient
    from redato_backend.portal.portal_app import app

    engine, _ = engine_e_schema
    import redato_backend.portal.db as dbmod
    original = dbmod._engine
    dbmod._engine = engine
    yield TestClient(app)
    dbmod._engine = original


@pytest.fixture
def bearer(world):
    from redato_backend.portal.auth.jwt_service import encode_token

    def _make(papel: str) -> Dict[str, str]:
        if papel == "professor":
            uid, esc = world["professor_id"], world["escola_id"]
        elif papel == "professor_outro":
            uid = world["professor_outro_id"]
            esc = world["escola_outra_id"]
        else:
            raise ValueError(papel)
        token, _ = encode_token(
            user_id=str(uid), papel="professor",
            escola_id=str(esc),
        )
        return {"Authorization": f"Bearer {token}"}

    return _make


# ──────────────────────────────────────────────────────────────────────
# Detalhe da reescrita — happy paths
# ──────────────────────────────────────────────────────────────────────

def test_get_detalhe_reescrita_completa_caso_feliz(client, world, bearer):
    r = client.get(
        f"/portal/partidas/{world['partida_id']}"
        f"/reescritas/{world['aluno_a1_id']}",
        headers=bearer("professor"),
    )
    assert r.status_code == 200, r.text
    data = r.json()
    # Estrutura geral
    assert "partida" in data
    assert "aluno" in data
    assert "cartas_escolhidas" in data
    assert "texto_montado" in data
    assert "reescrita" in data

    # Partida
    assert data["partida"]["grupo_codigo"] == "Grupo Teste"
    assert data["partida"]["tema"] == "saude_mental"
    assert data["partida"]["nome_humano_tema"] == "Saúde Mental"
    assert data["partida"]["atividade_nome"].startswith("OF13 — ")

    # Aluno
    assert data["aluno"]["nome"] == "Aluna A"
    assert data["aluno"]["aluno_turma_id"] == str(world["aluno_a1_id"])

    # Reescrita + redato_output
    assert data["reescrita"]["texto"].startswith("Reescrita completa")
    assert data["reescrita"]["redato_output"] is not None
    assert data["reescrita"]["redato_output"]["nota_total_enem"] == 880
    assert data["reescrita"]["redato_output"]["transformacao_cartas"] == 80
    assert data["reescrita"]["elapsed_ms"] == 12340

    # Cartas escolhidas: 2 estruturais (E01, E10) + 2 lacunas (P01, R01)
    cods = [c["codigo"] for c in data["cartas_escolhidas"]]
    assert cods == ["E01", "E10", "P01", "R01"]
    e01 = data["cartas_escolhidas"][0]
    assert e01["tipo"] == "ESTRUTURAL"
    assert e01["secao"] == "ABERTURA"
    assert e01["cor"] == "AZUL"
    p01 = data["cartas_escolhidas"][2]
    assert p01["tipo"] == "PROBLEMA"
    assert p01["secao"] is None
    assert p01["cor"] is None


def test_get_detalhe_reescrita_sem_redato_output(client, world, bearer):
    """Aluno B mandou reescrita mas Claude falhou — redato_output=null.
    UI vai mostrar 'avaliação pendente'."""
    r = client.get(
        f"/portal/partidas/{world['partida_id']}"
        f"/reescritas/{world['aluno_a2_id']}",
        headers=bearer("professor"),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["reescrita"]["redato_output"] is None
    assert data["reescrita"]["texto"].startswith("Reescrita do aluno B")


def test_get_detalhe_reescrita_com_flag_dh_true(
    client, world, bearer, engine_e_schema,
):
    """Reescrita marcada por DH — redato_output.flags.desrespeito... =
    true. UI mostra banner vermelho."""
    from sqlalchemy.orm import Session
    from redato_backend.portal.models import ReescritaIndividual

    engine, _ = engine_e_schema
    with Session(engine) as s:
        rs = s.query(ReescritaIndividual).filter_by(
            partida_id=world["partida_id"],
            aluno_turma_id=world["aluno_a1_id"],
        ).one()
        # Modifica redato_output pra simular flag DH ativada
        ro = dict(rs.redato_output or {})
        ro["flags"] = {**ro.get("flags", {}), "desrespeito_direitos_humanos": True}
        rs.redato_output = ro
        s.commit()

    r = client.get(
        f"/portal/partidas/{world['partida_id']}"
        f"/reescritas/{world['aluno_a1_id']}",
        headers=bearer("professor"),
    )
    assert r.status_code == 200
    data = r.json()
    assert data["reescrita"]["redato_output"]["flags"]["desrespeito_direitos_humanos"] is True

    # Reverte pro state normal pra não afetar outros tests
    with Session(engine) as s:
        rs = s.query(ReescritaIndividual).filter_by(
            partida_id=world["partida_id"],
            aluno_turma_id=world["aluno_a1_id"],
        ).one()
        ro = dict(rs.redato_output or {})
        ro["flags"] = {**ro.get("flags", {}), "desrespeito_direitos_humanos": False}
        rs.redato_output = ro
        s.commit()


# ──────────────────────────────────────────────────────────────────────
# Permissões + 404
# ──────────────────────────────────────────────────────────────────────

def test_get_detalhe_outro_professor_403(client, world, bearer):
    """Professor de outra escola — 403."""
    r = client.get(
        f"/portal/partidas/{world['partida_id']}"
        f"/reescritas/{world['aluno_a1_id']}",
        headers=bearer("professor_outro"),
    )
    assert r.status_code == 403


def test_get_detalhe_partida_inexistente_404(client, bearer, world):
    r = client.get(
        f"/portal/partidas/{uuid.uuid4()}"
        f"/reescritas/{world['aluno_a1_id']}",
        headers=bearer("professor"),
    )
    assert r.status_code == 404


def test_get_detalhe_aluno_fora_da_partida_404(client, world, bearer):
    """Aluno existe mas não pertence à partida — 404."""
    aluno_externo = uuid.uuid4()
    r = client.get(
        f"/portal/partidas/{world['partida_id']}"
        f"/reescritas/{aluno_externo}",
        headers=bearer("professor"),
    )
    assert r.status_code == 404


def test_get_detalhe_aluno_sem_reescrita_404(client, world, bearer):
    """Aluno C pertence à partida mas ainda não enviou reescrita — 404
    com mensagem específica. UI vai navegar pra cá só pra alunos
    avaliados (link condicional), mas defesa ok."""
    r = client.get(
        f"/portal/partidas/{world['partida_id']}"
        f"/reescritas/{world['aluno_a3_id']}",
        headers=bearer("professor"),
    )
    assert r.status_code == 404
    assert "Reescrita" in r.json()["detail"]


# ──────────────────────────────────────────────────────────────────────
# PartidaResumo agora inclui reescrita_status por aluno
# ──────────────────────────────────────────────────────────────────────

def test_partida_resumo_inclui_reescrita_status_por_aluno(
    client, world, bearer,
):
    """GET /atividades/{id}/partidas (Passo 3) agora retorna status
    da reescrita pra cada aluno. Sem isso, UI não consegue renderizar
    badge por aluno na lista de partidas."""
    r = client.get(
        f"/portal/atividades/{world['ativ_id']}/partidas",
        headers=bearer("professor"),
    )
    assert r.status_code == 200
    partidas = r.json()
    assert len(partidas) == 1
    partida = partidas[0]
    assert partida["grupo_codigo"] == "Grupo Teste"

    # Status por aluno
    by_id: Dict[str, str] = {
        a["aluno_turma_id"]: a["reescrita_status"]
        for a in partida["alunos"]
    }
    assert by_id[str(world["aluno_a1_id"])] == "avaliada"
    assert by_id[str(world["aluno_a2_id"])] == "em_avaliacao"
    assert by_id[str(world["aluno_a3_id"])] == "pendente"
