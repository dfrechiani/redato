"""E2E do fluxo completo de partida + avaliação Redato (Fase 2 passo 5).

Continuação dos testes do Passo 4 (`test_bot_jogo_partida.py`). Aqui
o bot recebe a reescrita, chama o pipeline `grade_jogo_redacao` (com
Claude API mockado), persiste `redato_output`, e responde com feedback
formatado.

Postgres real obrigatório (autouse fixtures isolam schema). Mock do
Claude via monkey-patch do entry point `grade_jogo_redacao` —
substituímos por funções determinísticas que retornam tool_args fixos.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL não definido — exige Postgres real",
)


# ──────────────────────────────────────────────────────────────────────
# Fixtures (espelha test_bot_jogo_partida.py)
# ──────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def engine_e_schema():
    from sqlalchemy import create_engine, text
    from redato_backend.portal.db import Base
    from redato_backend.portal import models  # noqa: F401

    test_schema = f"bot_jogo_completa_test_{uuid.uuid4().hex[:8]}"
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
    from sqlalchemy.orm import Session
    from redato_backend.portal.auth.password import hash_senha
    from redato_backend.portal.models import (
        AlunoTurma, Atividade, CartaEstrutural, CartaLacuna, Escola,
        JogoMinideck, Missao, PartidaJogo, Professor, Turma,
    )

    engine, _ = engine_e_schema

    with Session(engine) as s:
        e = Escola(codigo=f"E-{uuid.uuid4().hex[:6]}", nome="Esc",
                    estado="SP", municipio="SP")
        s.add(e); s.flush()
        p = Professor(escola_id=e.id, nome="P",
                       email=f"p-{uuid.uuid4().hex[:6]}@x",
                       senha_hash=hash_senha("Senha123Forte"))
        s.add(p); s.flush()
        t = Turma(escola_id=e.id, professor_id=p.id, codigo="2A",
                   serie="2S",
                   codigo_join=f"TURMA-{uuid.uuid4().hex[:6]}",
                   ano_letivo=2026)
        s.add(t); s.flush()
        a1 = AlunoTurma(turma_id=t.id, nome="Aluna A",
                         telefone=f"+5511{uuid.uuid4().hex[:8]}")
        s.add(a1); s.flush()

        m = Missao(codigo=f"RJ2-{uuid.uuid4().hex[:6]}", serie="2S",
                    oficina_numero=13, titulo="Jogo Completo",
                    modo_correcao="completo")
        s.add(m); s.flush()

        agora = datetime.now(timezone.utc)
        ativ = Atividade(
            turma_id=t.id, missao_id=m.id,
            data_inicio=agora - timedelta(hours=1),
            data_fim=agora + timedelta(days=14),
            criada_por_professor_id=p.id,
        )
        s.add(ativ); s.flush()

        # Catálogo mínimo (10 estruturais + cartas dos 7 tipos)
        ESTRUTURAIS = [
            ("E01", "ABERTURA", "AZUL",
             "No Brasil, [PROBLEMA] persiste. Conforme [REPERTORIO], demanda atenção.",
             ["PROBLEMA", "REPERTORIO"]),
            ("E10", "TESE", "AZUL",
             "Cenário impulsionado por [PALAVRA_CHAVE].",
             ["PALAVRA_CHAVE"]),
            ("E17", "TOPICO_DEV1", "AMARELO",
             "Em primeira análise, [PROBLEMA] liga-se a [PALAVRA_CHAVE].",
             ["PROBLEMA", "PALAVRA_CHAVE"]),
            ("E19", "ARGUMENTO_DEV1", "AMARELO",
             "Tal realidade é agravada por [PALAVRA_CHAVE].",
             ["PALAVRA_CHAVE"]),
            ("E21", "REPERTORIO_DEV1", "AMARELO",
             "Comprovado por [REPERTORIO].",
             ["REPERTORIO"]),
            ("E33", "TOPICO_DEV2", "VERDE",
             "Outro fator: [PALAVRA_CHAVE] amplia [PROBLEMA].",
             ["PALAVRA_CHAVE", "PROBLEMA"]),
            ("E35", "ARGUMENTO_DEV2", "VERDE",
             "Há prejuízos para [PALAVRA_CHAVE].",
             ["PALAVRA_CHAVE"]),
            ("E37", "REPERTORIO_DEV2", "VERDE",
             "Análise em [REPERTORIO].",
             ["REPERTORIO"]),
            ("E49", "RETOMADA", "LARANJA",
             "Evidencia-se que [PROBLEMA] exige [ACAO_MEIO].",
             ["PROBLEMA", "ACAO_MEIO"]),
            ("E51", "PROPOSTA", "LARANJA",
             "[AGENTE] tem como prioridade [ACAO_MEIO].",
             ["AGENTE", "ACAO_MEIO"]),
        ]
        for i, (cod, sec, cor, tx, lac) in enumerate(ESTRUTURAIS):
            s.add(CartaEstrutural(
                codigo=cod, secao=sec, cor=cor,
                texto=tx, lacunas=lac, ordem=i + 1,
            ))
        s.flush()

        md = JogoMinideck(
            tema="saude_mental", nome_humano="Saúde Mental",
            serie="2S", ativo=True,
        )
        s.add(md); s.flush()

        for cod, tipo, cont in [
            ("P01", "PROBLEMA", "estigma social"),
            ("P05", "PROBLEMA", "falta de profissionais"),
            ("R01", "REPERTORIO", "OMS"),
            ("K01", "PALAVRA_CHAVE", "investimento"),
            ("A01", "AGENTE", "Ministério da Saúde"),
            ("AC07", "ACAO", "ampliar CAPS"),
            ("ME04", "MEIO", "via emendas"),
            ("F02", "FIM", "garantir tratamento"),
        ]:
            s.add(CartaLacuna(
                minideck_id=md.id, tipo=tipo, codigo=cod,
                conteudo=cont,
            ))
        s.flush()

        partida = PartidaJogo(
            atividade_id=ativ.id, minideck_id=md.id,
            grupo_codigo="Grupo Teste",
            cartas_escolhidas={
                "_alunos_turma_ids": [str(a1.id)],
            },
            texto_montado="",
            prazo_reescrita=agora + timedelta(days=7),
            criada_por_professor_id=p.id,
        )
        s.add(partida); s.flush()

        s.commit()

        return {
            "engine": engine,
            "phone_a1": a1.telefone,
            "aluno_a1_id": a1.id,
            "ativ_id": ativ.id,
            "partida_id": partida.id,
            "minideck_id": md.id,
        }


@pytest.fixture(autouse=True)
def patch_engine(engine_e_schema):
    engine, _ = engine_e_schema
    import redato_backend.portal.db as dbmod
    original = dbmod._engine
    dbmod._engine = engine
    yield
    dbmod._engine = original


@pytest.fixture(autouse=True)
def isolar_sqlite_fsm(monkeypatch, tmp_path):
    db_path = tmp_path / "test_redato.db"
    monkeypatch.setenv("REDATO_WHATSAPP_DB", str(db_path))


@pytest.fixture(autouse=True)
def reset_partida_estado(world):
    """Reseta partida + apaga reescritas antes de cada test."""
    from sqlalchemy import delete
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import (
        PartidaJogo, ReescritaIndividual,
    )

    with Session(get_engine()) as s:
        s.execute(delete(ReescritaIndividual).where(
            ReescritaIndividual.partida_id == world["partida_id"],
        ))
        partida = s.get(PartidaJogo, world["partida_id"])
        partida.cartas_escolhidas = {
            "_alunos_turma_ids": [str(world["aluno_a1_id"])],
        }
        partida.texto_montado = ""
        s.commit()
    yield


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _send(phone, *, text=None, image_path=None):
    from redato_backend.whatsapp.bot import handle_message
    return handle_message(phone, text=text, image_path=image_path)


def _seed_aluno_ready(phone):
    from redato_backend.whatsapp import persistence as P
    P.init_db()
    P.upsert_aluno(phone, estado="READY")


def _codigos_completos():
    return ("E01, E10, E17, E19, E21, E33, E35, E37, E49, E51, "
            "P01, R01, K01, A01, AC07, ME04, F02")


def _reescrita_longa() -> str:
    """Texto >= 50 chars."""
    return (
        "No Brasil, o estigma social associado aos transtornos mentais "
        "configura uma das principais barreiras ao acesso à saúde "
        "psicológica. Segundo a OMS, essa exclusão é estrutural."
    )


def _mock_response_caso_feliz() -> Dict[str, Any]:
    """Response simulada do Claude pra reescrita autoral substancial."""
    return {
        "modo": "jogo_redacao",
        "tema_minideck": "saude_mental",
        "notas_enem": {"c1": 200, "c2": 200, "c3": 160, "c4": 160, "c5": 160},
        "nota_total_enem": 880,
        "transformacao_cartas": 80,
        "sugestoes_cartas_alternativas": [],
        "flags": {
            "copia_literal_das_cartas": False,
            "cartas_mal_articuladas": False,
            "fuga_do_tema_do_minideck": False,
            "tipo_textual_inadequado": False,
            "desrespeito_direitos_humanos": False,
        },
        "feedback_aluno": {
            "acertos": ["Tese bem definida.", "Articulação coesa."],
            "ajustes": ["Aprofundar o repertório de OMS."],
        },
        "feedback_professor": {
            "pontos_fortes": ["Recorte temático preservado."],
            "pontos_fracos": ["Repertório poderia ser mais detalhado."],
            "padrao_falha": "repertório de bolso parcial",
            "transferencia_competencia": "treinar uso de dados verificáveis",
        },
        "_mission": {"mode": "jogo_redacao"},
    }


def _mock_response_copia_literal() -> Dict[str, Any]:
    out = _mock_response_caso_feliz()
    out["transformacao_cartas"] = 10
    out["flags"]["copia_literal_das_cartas"] = True
    out["notas_enem"] = {"c1": 160, "c2": 80, "c3": 80, "c4": 80, "c5": 80}
    out["nota_total_enem"] = 480
    return out


def _mock_response_com_sugestoes() -> Dict[str, Any]:
    out = _mock_response_caso_feliz()
    out["sugestoes_cartas_alternativas"] = [
        {
            "codigo_original": "P01",
            "codigo_sugerido": "P05",
            "motivo": "P05 dá mais especificidade ao recorte temático.",
        },
    ]
    return out


# ──────────────────────────────────────────────────────────────────────
# Casos
# ──────────────────────────────────────────────────────────────────────

def test_reescrita_chama_claude_persiste_e_responde_feedback(
    world, monkeypatch,
):
    """Caso feliz E2E: aluno manda reescrita → bot persiste → chama
    Claude (mock) → atualiza redato_output → formata feedback."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import ReescritaIndividual

    # Mock grade_jogo_redacao (não chama Anthropic real)
    mock_resposta = _mock_response_caso_feliz()
    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        MagicMock(return_value=mock_resposta),
    )

    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")  # → AGUARDANDO_CARTAS
    _send(world["phone_a1"], text=_codigos_completos())  # → REVISANDO

    # Manda reescrita
    out = _send(world["phone_a1"], text=_reescrita_longa())
    assert len(out) == 1
    feedback = out[0]
    # Feedback formatado contém marcas do render
    assert "Reescrita avaliada" in feedback
    assert "880/1000" in feedback
    assert "Transformação das cartas" in feedback
    assert "80/100" in feedback or "80/100 — " in feedback
    assert "Tese bem definida" in feedback or "ajustes" in feedback.lower()

    # Estado voltou pra READY
    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a1"])
    assert aluno["estado"] == "READY"

    # redato_output persistido
    with Session(get_engine()) as s:
        rs = s.execute(
            select(ReescritaIndividual).where(
                ReescritaIndividual.partida_id == world["partida_id"],
                ReescritaIndividual.aluno_turma_id == world["aluno_a1_id"],
            )
        ).scalar_one()
        assert rs.redato_output is not None
        assert rs.redato_output["nota_total_enem"] == 880
        assert rs.redato_output["transformacao_cartas"] == 80
        assert rs.elapsed_ms is not None and rs.elapsed_ms >= 0


def test_reescrita_com_copia_literal_mostra_score_baixo_no_feedback(
    world, monkeypatch,
):
    """Aluno copiou literal — render mostra "cópia das cartas"."""
    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        MagicMock(return_value=_mock_response_copia_literal()),
    )

    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos())
    out = _send(world["phone_a1"], text=_reescrita_longa())
    assert len(out) == 1
    feedback = out[0]
    assert "10/100" in feedback or "cópia" in feedback.lower()


def test_reescrita_com_sugestoes_renderiza_secao(world, monkeypatch):
    """Sugestões aparecem como bloco "Cartas alternativas que valem testar"."""
    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        MagicMock(return_value=_mock_response_com_sugestoes()),
    )

    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos())
    out = _send(world["phone_a1"], text=_reescrita_longa())
    feedback = out[0]
    assert "Cartas alternativas" in feedback
    assert "P01 → P05" in feedback


def test_claude_timeout_responde_mensagem_temporaria_persistencia_ok(
    world, monkeypatch,
):
    """Claude timeout — bot avisa "demorou, vai chegar em alguns
    minutos". Reescrita JÁ persistida no DB com redato_output=null
    (professor pode reprocessar via UI futura)."""
    import anthropic
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import ReescritaIndividual

    def _raise_timeout(*a, **kw):
        raise anthropic.APITimeoutError(MagicMock())

    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        _raise_timeout,
    )

    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos())
    out = _send(world["phone_a1"], text=_reescrita_longa())
    assert len(out) == 1
    assert ("avaliação" in out[0].lower() or "demor" in out[0].lower()
             or "alguns minutos" in out[0].lower())

    # Reescrita persistida com redato_output=null
    with Session(get_engine()) as s:
        rs = s.execute(
            select(ReescritaIndividual).where(
                ReescritaIndividual.partida_id == world["partida_id"],
                ReescritaIndividual.aluno_turma_id == world["aluno_a1_id"],
            )
        ).scalar_one()
        assert rs.redato_output is None  # Passo 6 reprocessa via UI


def test_claude_erro_generico_avisa_professor_vai_reprocessar(
    world, monkeypatch,
):
    """Erro não-timeout → mensagem genérica, reescrita persiste pra
    reprocesso futuro."""
    def _raise_generic(*a, **kw):
        raise ValueError("erro qualquer no pipeline")

    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        _raise_generic,
    )

    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos())
    out = _send(world["phone_a1"], text=_reescrita_longa())
    assert len(out) == 1
    msg = out[0].lower()
    assert "professor" in msg or "técnico" in msg or "problema" in msg


def test_resubmissao_bloqueada_apos_avaliacao(world, monkeypatch):
    """Aluno mandou reescrita + recebeu feedback. Tenta enviar de novo
    (qualquer texto) — bot detecta que partida pendente sumiu (já tem
    reescrita) e cai em fluxo READY normal (sem partida)."""
    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        MagicMock(return_value=_mock_response_caso_feliz()),
    )

    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos())
    _send(world["phone_a1"], text=_reescrita_longa())

    # Segunda mensagem após avaliação — não deve disparar fluxo de
    # partida (find_partida_pendente_para_aluno retorna None porque
    # já existe reescrita do aluno).
    from redato_backend.whatsapp import portal_link as PL
    pendente = PL.find_partida_pendente_para_aluno(world["phone_a1"])
    assert pendente is None


def test_redato_output_inclui_metadata_mission(world, monkeypatch):
    """`redato_output._mission` tem mode + model — dashboard usa
    pra distinguir avaliações."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import ReescritaIndividual

    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        MagicMock(return_value=_mock_response_caso_feliz()),
    )

    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos())
    _send(world["phone_a1"], text=_reescrita_longa())

    with Session(get_engine()) as s:
        rs = s.execute(
            select(ReescritaIndividual).where(
                ReescritaIndividual.aluno_turma_id == world["aluno_a1_id"],
            )
        ).scalar_one()
        assert rs.redato_output["_mission"]["mode"] == "jogo_redacao"
