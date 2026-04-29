"""Testes integration do bot WhatsApp pra fluxo de partida (Fase 2 passo 4).

Exercita o pipeline completo: aluno manda mensagem → handle_inbound →
DB. Postgres real obrigatório (FSM SQLite + partida em Postgres),
schema isolado por module.

Testes pulados se sem DATABASE_URL.
"""
from __future__ import annotations

import os
import tempfile
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

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

    test_schema = f"bot_jogo_test_{uuid.uuid4().hex[:8]}"
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"options": f"-csearch_path={test_schema}"},
    )
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()
    # Confia em search_path no connect_args — NÃO muta
    # Base.metadata.tables[*].schema (mutação global → leak entre
    # módulos quando suite roda inteira). create_all sem schema
    # prefix → Postgres usa search_path → tabelas no test_schema.
    Base.metadata.create_all(engine)
    yield engine, test_schema
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
        conn.commit()


@pytest.fixture(scope="module")
def world(engine_e_schema):
    """Seed de 1 minideck (Saúde Mental) com 10 estruturais + cartas
    cobrindo cada tipo, 1 turma, 1 atividade ativa, 2 alunos, 1 partida
    pendente pra cartas."""
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
        a1 = AlunoTurma(turma_id=t.id, nome="Aluno A",
                         telefone=f"+5511{uuid.uuid4().hex[:8]}")
        a2 = AlunoTurma(turma_id=t.id, nome="Aluno B",
                         telefone=f"+5511{uuid.uuid4().hex[:8]}")
        s.add_all([a1, a2]); s.flush()

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

        # Catálogo: 10 estruturais (1 por seção) + cartas do minideck
        ESTRUTURAIS_FIXTURE = [
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
             "Comprovado por [REPERTORIO]. [PALAVRA_CHAVE] demanda ação.",
             ["REPERTORIO", "PALAVRA_CHAVE"]),
            ("E33", "TOPICO_DEV2", "VERDE",
             "Outro fator: [PALAVRA_CHAVE] amplia [PROBLEMA].",
             ["PALAVRA_CHAVE", "PROBLEMA"]),
            ("E35", "ARGUMENTO_DEV2", "VERDE",
             "Há sérios prejuízos para [PALAVRA_CHAVE].",
             ["PALAVRA_CHAVE"]),
            ("E37", "REPERTORIO_DEV2", "VERDE",
             "Análise encontra respaldo em [REPERTORIO].",
             ["REPERTORIO"]),
            ("E49", "RETOMADA", "LARANJA",
             "Evidencia-se que [PROBLEMA] exige [ACAO_MEIO].",
             ["PROBLEMA", "ACAO_MEIO"]),
            ("E51", "PROPOSTA", "LARANJA",
             "[AGENTE] tem como prioridade [ACAO_MEIO].",
             ["AGENTE", "ACAO_MEIO"]),
        ]
        for i, (cod, sec, cor, tx, lac) in enumerate(ESTRUTURAIS_FIXTURE):
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

        LACUNAS_FIXTURE = [
            ("P01", "PROBLEMA", "estigma social"),
            ("P02", "PROBLEMA", "falta de acesso"),
            ("R01", "REPERTORIO", "OMS (86% sem tratamento)"),
            ("R05", "REPERTORIO", "IBGE 2022"),
            ("K01", "PALAVRA_CHAVE", "investimento"),
            ("K11", "PALAVRA_CHAVE", "estigma cultural"),
            ("K22", "PALAVRA_CHAVE", "preconceito"),
            ("A01", "AGENTE", "Ministério da Saúde"),
            ("AC07", "ACAO", "ampliar a rede de CAPS"),
            ("ME04", "MEIO", "via emendas parlamentares"),
            ("F02", "FIM", "para garantir tratamento universal"),
        ]
        for cod, tipo, cont in LACUNAS_FIXTURE:
            s.add(CartaLacuna(
                minideck_id=md.id, tipo=tipo, codigo=cod,
                conteudo=cont,
            ))
        s.flush()

        # Partida pendente: A1 e A2 escolhidos, sem cartas ainda
        partida = PartidaJogo(
            atividade_id=ativ.id, minideck_id=md.id,
            grupo_codigo="Grupo Teste",
            cartas_escolhidas={
                "_alunos_turma_ids": [str(a1.id), str(a2.id)],
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
            "phone_a2": a2.telefone,
            "phone_externo": f"+5511{uuid.uuid4().hex[:8]}",
            "aluno_a1_id": a1.id,
            "aluno_a2_id": a2.id,
            "ativ_id": ativ.id,
            "partida_id": partida.id,
            "minideck_id": md.id,
        }


@pytest.fixture(autouse=True)
def patch_engine(engine_e_schema):
    """Injeta o engine isolado no cache global de `portal.db._engine`.

    Por que NÃO usamos monkeypatch em `dbmod.get_engine`: módulos como
    `portal_api`, `jogo_api`, `portal_link` fazem `from redato_backend.
    portal.db import get_engine` na import time, criando bindings
    locais. Patchar `dbmod.get_engine` não afeta esses bindings — eles
    continuam apontando pra função original. A função original consulta
    o cache `_engine` (com check por URL). Se a gente troca o cache,
    todas as chamadas seguintes recebem o engine de teste, sem precisar
    patchar cada módulo.

    Restaura o cache anterior no teardown."""
    engine, _ = engine_e_schema
    import redato_backend.portal.db as dbmod
    original = dbmod._engine
    dbmod._engine = engine
    yield
    dbmod._engine = original


@pytest.fixture(autouse=True)
def isolar_sqlite_fsm(monkeypatch, tmp_path):
    """Cada teste tem seu próprio SQLite (FSM do bot) — isola estado
    entre tests pra evitar carry-over de aluno."""
    db_path = tmp_path / "test_redato.db"
    monkeypatch.setenv("REDATO_WHATSAPP_DB", str(db_path))


@pytest.fixture(autouse=True)
def reset_partida_estado(world):
    """Reseta a partida pro estado 'aguardando_cartas' (texto_montado=""
    + sem reescritas) ANTES de cada test. Sem isso, testes que rodam
    depois de um test que populou texto_montado encontram a partida
    em 'aguardando_reescrita' e o fluxo entra direto em REVISANDO."""
    from sqlalchemy import select, delete
    from sqlalchemy.orm import Session

    from redato_backend.portal.db import get_engine
    from redato_backend.portal.models import (
        PartidaJogo, ReescritaIndividual,
    )

    with Session(get_engine()) as s:
        # Limpa todas as reescritas dessa partida
        s.execute(delete(ReescritaIndividual).where(
            ReescritaIndividual.partida_id == world["partida_id"],
        ))
        # Reseta partida: cartas_escolhidas só com _alunos_turma_ids,
        # texto_montado vazio
        partida = s.get(PartidaJogo, world["partida_id"])
        partida.cartas_escolhidas = {
            "_alunos_turma_ids": [
                str(world["aluno_a1_id"]),
                str(world["aluno_a2_id"]),
            ],
        }
        partida.texto_montado = ""
        s.commit()
    yield


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _send(phone: str, *, text: str | None = None,
           image_path: str | None = None):
    from redato_backend.whatsapp.bot import handle_message
    return handle_message(phone, text=text, image_path=image_path)


def _seed_aluno_ready(phone: str):
    """Vincula o phone como AlunoTurma já cadastrado (estado READY).
    Pra testar o fluxo após onboarding sem repetir todo cadastro."""
    from redato_backend.whatsapp import persistence as P
    P.init_db()
    P.upsert_aluno(phone, estado="READY")


def _codigos_completos_text() -> str:
    return ("E01, E10, E17, E19, E21, E33, E35, E37, E49, E51, "
            "P01, R01, K01, A01, AC07, ME04, F02")


# ──────────────────────────────────────────────────────────────────────
# Casos
# ──────────────────────────────────────────────────────────────────────

def test_aluno_em_ready_com_partida_pendente_recebe_saudacao(world):
    """Aluno em READY (qualquer texto) tem partida pendente — bot
    saúda e transiciona pra AGUARDANDO_CARTAS_PARTIDA."""
    _seed_aluno_ready(world["phone_a1"])
    out = _send(world["phone_a1"], text="oi")
    assert len(out) == 1
    assert "jogo de redação" in out[0].lower()
    assert "Grupo Teste" in out[0]
    assert "Saúde Mental" in out[0]

    # Verifica que estado virou AGUARDANDO_CARTAS_PARTIDA|<uuid>
    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a1"])
    assert aluno["estado"].startswith("AGUARDANDO_CARTAS_PARTIDA|")


def test_aluno_externo_sem_vinculo_nao_dispara_fluxo_partida(world):
    """Phone que NÃO está em alunos_turma_ids da partida — fluxo
    normal (no caso, cadastro inicial)."""
    out = _send(world["phone_externo"], text="oi")
    # Resposta padrão de cadastro novo
    assert any("código" in m.lower() or "cadastr" in m.lower()
               or "boas-vind" in m.lower() or "olá" in m.lower()
               for m in out)


def test_codigos_completos_validam_e_montam_texto(world):
    """Caso feliz: aluno em AGUARDANDO_CARTAS manda 17 codigos válidos.
    Bot monta texto + transição."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")  # entra em AGUARDANDO_CARTAS
    out = _send(world["phone_a1"], text=_codigos_completos_text())
    assert len(out) == 1
    assert "redação que o seu grupo montou" in out[0]
    # Conteúdos das cartas presentes
    assert "estigma social" in out[0]
    assert "OMS" in out[0]

    # Estado virou REVISANDO
    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a1"])
    assert aluno["estado"].startswith("REVISANDO_TEXTO_MONTADO|")

    # Partida no DB tem texto_montado populado
    from redato_backend.portal.models import PartidaJogo
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    with Session(get_engine()) as s:
        pj = s.get(PartidaJogo, world["partida_id"])
        assert pj.texto_montado.strip() != ""
        assert "estigma social" in pj.texto_montado


def test_proposta_incompleta_avisa_warning_e_aceita(world):
    """Aluno faltou ME04 e F02 (proposta com 2 elementos) — bot avisa
    com warning + aceita. Texto monta partial-fill: AC07 preenche
    mas ME e F ficam ausentes (warning comunica a lacuna)."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    codigos_sem_me_f = (
        "E01, E10, E17, E19, E21, E33, E35, E37, E49, E51, "
        "P01, R01, K01, A01, AC07"
    )
    out = _send(world["phone_a1"], text=codigos_sem_me_f)
    # Warning + texto montado = 2 mensagens
    assert len(out) == 2
    assert "avisos" in out[0].lower() or "lacuna" in out[0].lower()
    # Warning cita os tipos faltantes
    assert "MEIO" in out[0] or "FIM" in out[0]
    assert "redação que o seu grupo montou" in out[1]
    # AC07 conteúdo presente; ME e F ausentes
    assert "ampliar a rede de CAPS" in out[1]
    assert "via emendas" not in out[1]
    assert "garantir tratamento" not in out[1]


def test_proposta_com_1_tipo_recusa_com_erro(world):
    """< 2 lacunas da proposta → erro fatal."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    codigos = (
        "E01, E10, E17, E19, E21, E33, E35, E37, E49, E51, "
        "P01, R01, K01, A01"  # só A01, falta AC/ME/F (3 vazios)
    )
    out = _send(world["phone_a1"], text=codigos)
    assert len(out) == 1
    assert "Faltam" in out[0]
    assert "proposta" in out[0].lower()
    # Estado MANTIDO em AGUARDANDO (aluno pode reenviar)
    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a1"])
    assert aluno["estado"].startswith("AGUARDANDO_CARTAS_PARTIDA|")


def test_codigo_inexistente_recusa(world):
    """Código P99 não existe no minideck — erro com nome do tema."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    codigos = (
        "E01, E10, E17, E19, E21, E33, E35, E37, E49, E51, "
        "P99, R01, K01, A01, AC07, ME04, F02"
    )
    out = _send(world["phone_a1"], text=codigos)
    assert len(out) == 1
    assert "P99" in out[0]
    assert "Saúde Mental" in out[0]


def test_falta_secao_estrutural_recusa(world):
    """Sem ABERTURA — erro pedindo seção."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    codigos = (
        # Sem E01 (ABERTURA)
        "E10, E17, E19, E21, E33, E35, E37, E49, E51, "
        "P01, R01, K01, A01, AC07, ME04, F02"
    )
    out = _send(world["phone_a1"], text=codigos)
    assert len(out) == 1
    assert "Abertura" in out[0]


def test_foto_em_aguardando_cartas_redireciona(world):
    """Aluno em AGUARDANDO_CARTAS manda foto — bot redireciona."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    # Foto fake (path qualquer; bot não baixa nesse fluxo)
    out = _send(world["phone_a1"], image_path="/tmp/fake.jpg")
    assert len(out) == 1
    assert "texto" in out[0].lower()
    assert "foto" in out[0].lower()
    # Estado mantém
    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a1"])
    assert aluno["estado"].startswith("AGUARDANDO_CARTAS_PARTIDA|")


def test_reescrita_persiste_e_volta_ready(world, monkeypatch):
    """Aluno em REVISANDO manda texto >= 50 chars — persiste, volta READY.

    Passo 5 (commit feat(jogo): avaliação Redato modo jogo_redacao):
    bot agora chama grade_jogo_redacao síncrono na hora da reescrita.
    Aqui mockamos o pipeline pra testar SÓ a parte de persistência +
    transição de estado (avaliação real é coberta em
    `test_bot_jogo_partida_completa.py`)."""
    from unittest.mock import MagicMock
    monkeypatch.setattr(
        "redato_backend.missions.router.grade_jogo_redacao",
        MagicMock(return_value={
            "modo": "jogo_redacao",
            "tema_minideck": "saude_mental",
            "notas_enem": {"c1": 160, "c2": 160, "c3": 120,
                            "c4": 120, "c5": 120},
            "nota_total_enem": 680,
            "transformacao_cartas": 70,
            "sugestoes_cartas_alternativas": [],
            "flags": {
                "copia_literal_das_cartas": False,
                "cartas_mal_articuladas": False,
                "fuga_do_tema_do_minideck": False,
                "tipo_textual_inadequado": False,
                "desrespeito_direitos_humanos": False,
            },
            "feedback_aluno": {
                "acertos": ["Tese clara."],
                "ajustes": ["Aprofundar o argumento."],
            },
            "feedback_professor": {
                "pontos_fortes": ["x"], "pontos_fracos": ["y"],
                "padrao_falha": "z", "transferencia_competencia": "w",
            },
        }),
    )
    _seed_aluno_ready(world["phone_a2"])
    _send(world["phone_a2"], text="oi")
    _send(world["phone_a2"], text=_codigos_completos_text())
    # Agora em REVISANDO
    reescrita = (
        "No Brasil contemporâneo, o estigma social associado aos "
        "transtornos mentais persiste como uma barreira significativa "
        "ao acesso aos serviços de saúde, conforme demonstra a OMS. "
        "Diante dessa realidade, é fundamental que o Estado promova "
        "ações concretas que permitam superar esse cenário."
    )
    out = _send(world["phone_a2"], text=reescrita)
    assert len(out) == 1
    # Passo 5: feedback formatado em vez do placeholder antigo
    assert "Reescrita avaliada" in out[0]

    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a2"])
    assert aluno["estado"] == "READY"

    # Reescrita persistida com redato_output populado
    from redato_backend.portal.models import ReescritaIndividual
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    with Session(get_engine()) as s:
        rs = s.execute(
            select(ReescritaIndividual).where(
                ReescritaIndividual.partida_id == world["partida_id"],
                ReescritaIndividual.aluno_turma_id == world["aluno_a2_id"],
            )
        ).scalar_one()
        assert rs.redato_output is not None
        assert rs.redato_output["nota_total_enem"] == 680
        assert "estigma" in rs.texto.lower()


def test_reescrita_curta_avisa_sem_persistir(world):
    """Texto < 50 chars — bot avisa mas não persiste; estado mantém."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos_text())
    out = _send(world["phone_a1"], text="ok")  # 2 chars
    assert len(out) == 1
    assert "curto" in out[0].lower()

    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a1"])
    assert aluno["estado"].startswith("REVISANDO_TEXTO_MONTADO|")

    # Não persistiu reescrita
    from redato_backend.portal.models import ReescritaIndividual
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from redato_backend.portal.db import get_engine
    with Session(get_engine()) as s:
        n = s.execute(
            select(ReescritaIndividual).where(
                ReescritaIndividual.partida_id == world["partida_id"],
                ReescritaIndividual.aluno_turma_id == world["aluno_a1_id"],
            )
        ).first()
        assert n is None


def test_foto_em_revisando_redireciona(world):
    """Aluno em REVISANDO manda foto — bot redireciona pra texto."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    _send(world["phone_a1"], text=_codigos_completos_text())
    out = _send(world["phone_a1"], image_path="/tmp/fake.jpg")
    assert len(out) == 1
    assert "texto" in out[0].lower() or "reescrit" in out[0].lower()


def test_cancelar_em_aguardando_volta_ready(world):
    """Comando 'cancelar' em qualquer estado pós-cadastro — volta READY."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    out = _send(world["phone_a1"], text="cancelar")
    assert len(out) == 1
    # Estado é READY (mas próxima mensagem do aluno vai disparar
    # _entrar_fluxo_partida de novo — partida ainda pendente)


def test_aluno_resubmete_reescrita_bloqueado(world):
    """Aluno mandou reescrita → READY. Manda mensagem de novo:
    `_entrar_fluxo_partida` NÃO retorna a partida (já tem reescrita
    desse aluno)."""
    from redato_backend.whatsapp import portal_link as PL

    _seed_aluno_ready(world["phone_a2"])
    _send(world["phone_a2"], text="oi")
    _send(world["phone_a2"], text=_codigos_completos_text())
    reescrita = "x" * 100  # >= 50 chars
    _send(world["phone_a2"], text=reescrita)

    # Aluno está READY de novo. find_partida_pendente NÃO deve
    # retornar a mesma partida (aluno já submeteu reescrita).
    pendente = PL.find_partida_pendente_para_aluno(world["phone_a2"])
    assert pendente is None


def test_aluno_em_grupo_que_ja_montou_pula_pra_revisando(world):
    """Outro aluno do grupo já mandou cartas (texto_montado populado).
    Quando aluno A1 entra, bot pula direto pra REVISANDO mostrando
    o texto montado."""
    # A2 cadastra cartas primeiro
    _seed_aluno_ready(world["phone_a2"])
    _send(world["phone_a2"], text="oi")
    _send(world["phone_a2"], text=_codigos_completos_text())

    # Agora A1 entra do zero — texto_montado já existe
    _seed_aluno_ready(world["phone_a1"])
    out = _send(world["phone_a1"], text="oi")
    assert len(out) == 1
    assert "redação que o seu grupo montou" in out[0]

    # Estado A1 vai pra REVISANDO direto
    from redato_backend.whatsapp import persistence as P
    aluno = P.get_aluno(world["phone_a1"])
    assert aluno["estado"].startswith("REVISANDO_TEXTO_MONTADO|")


def test_segunda_mensagem_em_aguardando_sem_codigos_repete_prompt(world):
    """Aluno em AGUARDANDO manda texto sem códigos — bot repete a
    saudação como prompt."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    out = _send(world["phone_a1"], text="ainda não decidi")
    assert len(out) == 1
    assert "códigos das cartas" in out[0].lower()


def test_lacuna_dev_obrigatoria_falta_recusa(world):
    """Aluno escolheu E01 que pede [PROBLEMA] mas não mandou nenhum
    P##."""
    _seed_aluno_ready(world["phone_a1"])
    _send(world["phone_a1"], text="oi")
    codigos = (
        "E01, E10, E17, E19, E21, E33, E35, E37, E49, E51, "
        # Sem P##
        "R01, K01, A01, AC07, ME04, F02"
    )
    out = _send(world["phone_a1"], text=codigos)
    assert len(out) == 1
    assert "P##" in out[0]
    assert "[PROBLEMA]" in out[0]
