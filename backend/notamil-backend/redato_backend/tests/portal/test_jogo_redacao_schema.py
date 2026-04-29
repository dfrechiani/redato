"""Testes do schema do jogo "Redação em Jogo" (Fase 2 passo 1).

Cobre 2 camadas:

1. **Validators Python** (sem DB) — `@validates` em CartaEstrutural
   (secao + cor) e CartaLacuna (tipo). Garante que typo no seed é
   pego antes do INSERT e a mensagem é útil.

2. **Constraints SQL** (Postgres) — CHECK + UNIQUE + 1:N de
   `partidas_jogo` com atividade. Pula automático se DATABASE_URL
   não estiver definido (rodar via `pytest` local sem Postgres é OK).

A camada (2) usa um schema Postgres isolado por test run pra não
sujar dev. Mesmo padrão de `backend/notamil-backend/scripts/test_m6_gestao.py`.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest


# ──────────────────────────────────────────────────────────────────────
# Camada 1 — validators Python (sem DB)
# ──────────────────────────────────────────────────────────────────────

def test_carta_estrutural_secao_invalida_raise_no_python():
    """Defesa-em-camada: validator Python pega secao errada antes do
    INSERT. Mensagem inclui valor recebido + lista válida — útil
    quando seed tem typo ('TOPICO_DEV3' por mal-copy)."""
    from redato_backend.portal.models import CartaEstrutural
    with pytest.raises(ValueError, match="secao='TOPICO_DEV3' inválida"):
        CartaEstrutural(
            codigo="E99", secao="TOPICO_DEV3", cor="AZUL",
            texto="x", lacunas=[], ordem=99,
        )


def test_carta_estrutural_secao_valida_passa():
    from redato_backend.portal.models import CartaEstrutural
    c = CartaEstrutural(
        codigo="E01", secao="ABERTURA", cor="AZUL",
        texto="x", lacunas=["PROBLEMA"], ordem=1,
    )
    assert c.secao == "ABERTURA"


def test_carta_estrutural_cor_invalida_raise():
    from redato_backend.portal.models import CartaEstrutural
    with pytest.raises(ValueError, match="cor='ROSA' inválida"):
        CartaEstrutural(
            codigo="E01", secao="ABERTURA", cor="ROSA",
            texto="x", lacunas=[], ordem=1,
        )


def test_carta_lacuna_tipo_invalido_raise():
    from redato_backend.portal.models import CartaLacuna
    with pytest.raises(ValueError, match="tipo='SLOGAN' inválido"):
        CartaLacuna(
            minideck_id=uuid.uuid4(), tipo="SLOGAN",
            codigo="P01", conteudo="x",
        )


def test_carta_lacuna_tipos_validos_passam():
    from redato_backend.portal.models import CartaLacuna, TIPOS_LACUNA
    # Sanity: cada um dos 7 tipos canônicos é aceito.
    for tipo in TIPOS_LACUNA:
        c = CartaLacuna(
            minideck_id=uuid.uuid4(), tipo=tipo,
            codigo=f"{tipo[0]}01", conteudo="x",
        )
        assert c.tipo == tipo


def test_cor_por_secao_cobre_todas_secoes():
    """Toda secao válida tem cor mapeada. Defensivo — esquecer de
    adicionar a entrada no map quebraria o seed silenciosamente
    (KeyError em runtime quando tipo novo aparecer no xlsx)."""
    from redato_backend.portal.models import (
        COR_POR_SECAO, SECOES_ESTRUTURAIS,
    )
    for secao in SECOES_ESTRUTURAIS:
        assert secao in COR_POR_SECAO, (
            f"secao={secao} sem entrada em COR_POR_SECAO"
        )


def test_secoes_constants_match_check_constraint():
    """SECOES_ESTRUTURAIS no models tem que estar em sync com a
    string do CheckConstraint na migration. Drift silencioso aqui
    geraria validação Python passando + Postgres rejeitando — pior
    DX possível."""
    from redato_backend.portal.models import SECOES_ESTRUTURAIS
    # Lê a migration e procura a string do CHECK.
    from pathlib import Path
    backend = Path(__file__).resolve().parents[3]
    mig = (
        backend / "redato_backend" / "portal" / "migrations" /
        "versions" / "h0a1b2c3d4e5_jogo_redacao_em_jogo.py"
    ).read_text()
    for secao in SECOES_ESTRUTURAIS:
        assert f"'{secao}'" in mig, (
            f"secao={secao} no models não aparece na migration h0a1*"
        )


# ──────────────────────────────────────────────────────────────────────
# Camada 2 — DB integration (Postgres requerido)
# ──────────────────────────────────────────────────────────────────────

# Pula bloco inteiro se DATABASE_URL não estiver definido. Permite
# rodar `pytest` local sem Postgres (test suite vira 6 testes em vez
# de 14). Em CI ou quando Daniel testa antes de aplicar, define
# DATABASE_URL e roda o suite completo.
pytestmark_db = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason=(
        "DATABASE_URL não definido — testes de schema Postgres "
        "exigem Postgres real (ARRAY/JSONB/CHECK). Rode com "
        "DATABASE_URL=postgresql://... pytest"
    ),
)


@pytest.fixture(scope="module")
def pg_session():
    """Cria schema isolado, aplica migrations até head, retorna
    Session SQLAlchemy. Schema é dropado no teardown."""
    pytestmark_db.func()  # força skip se sem DATABASE_URL

    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import Session

    from redato_backend.portal.db import Base
    from redato_backend.portal import models  # noqa: F401

    test_schema = f"jogo_test_{uuid.uuid4().hex[:8]}"
    engine = create_engine(
        os.environ["DATABASE_URL"],
        connect_args={"options": f"-csearch_path={test_schema}"},
    )
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{test_schema}"'))
        conn.commit()
    # Aplica todas as tabelas do metadata (equivalente a alembic upgrade
    # head pra esse schema isolado).
    for table in Base.metadata.tables.values():
        table.schema = test_schema
    Base.metadata.create_all(engine)

    session = Session(engine)
    yield session

    session.close()
    with engine.connect() as conn:
        conn.execute(text(f'DROP SCHEMA "{test_schema}" CASCADE'))
        conn.commit()
    for table in Base.metadata.tables.values():
        table.schema = None


@pytestmark_db
def test_minideck_e_carta_lacuna_select_funciona(pg_session):
    """Cria minideck + carta_lacuna referenciando + verifica SELECT
    com joinedload puxa a relação."""
    from redato_backend.portal.models import CartaLacuna, JogoMinideck

    md = JogoMinideck(
        tema="saude_mental",
        nome_humano="Saúde Mental",
        serie="2S",
        descricao="Tema piloto da Fase 2",
    )
    pg_session.add(md)
    pg_session.flush()

    carta = CartaLacuna(
        minideck_id=md.id, tipo="PROBLEMA",
        codigo="P01",
        conteudo="estigma social associado aos transtornos mentais",
    )
    pg_session.add(carta)
    pg_session.commit()

    # SELECT roundtrip
    pg_session.refresh(md)
    assert len(md.cartas_lacuna) == 1
    assert md.cartas_lacuna[0].codigo == "P01"


@pytestmark_db
def test_check_constraint_secao_invalida_em_estrutural(pg_session):
    from sqlalchemy import text
    with pytest.raises(Exception):  # Postgres IntegrityError ou cousin
        # INSERT direto via SQL pra contornar o validator Python e
        # exercitar SOMENTE a CHECK constraint do banco.
        pg_session.execute(text(
            "INSERT INTO cartas_estruturais "
            "(id, codigo, secao, cor, texto, lacunas, ordem, created_at) "
            "VALUES (gen_random_uuid(), 'E99', 'INVALIDA', 'AZUL', "
            "'x', ARRAY[]::text[], 99, now())"
        ))
        pg_session.commit()
    pg_session.rollback()


@pytestmark_db
def test_check_constraint_tipo_invalido_em_lacuna(pg_session):
    from sqlalchemy import text
    from redato_backend.portal.models import JogoMinideck
    md = JogoMinideck(tema="t1", nome_humano="T1")
    pg_session.add(md)
    pg_session.flush()
    with pytest.raises(Exception):
        pg_session.execute(text(
            f"INSERT INTO cartas_lacuna "
            f"(id, minideck_id, tipo, codigo, conteudo, created_at) "
            f"VALUES (gen_random_uuid(), '{md.id}', 'TIPO_INVALIDO', "
            f"'X01', 'conteudo', now())"
        ))
        pg_session.commit()
    pg_session.rollback()


@pytestmark_db
def test_unique_partida_aluno_em_reescritas_individuais(pg_session):
    """Aluno tenta enviar 2 reescritas pra mesma partida — segundo
    INSERT bate UNIQUE constraint."""
    from sqlalchemy.exc import IntegrityError
    from redato_backend.portal.models import (
        AlunoTurma, Atividade, Escola, JogoMinideck, Missao,
        PartidaJogo, Professor, ReescritaIndividual, Turma,
    )

    # Setup mínimo: escola → professor → turma → aluno → missao →
    # atividade → minideck → partida → 2 tentativas de reescritas.
    escola = Escola(codigo="E1", nome="x", estado="SP", municipio="x")
    pg_session.add(escola); pg_session.flush()

    prof = Professor(escola_id=escola.id, nome="P", email=f"p{uuid.uuid4().hex[:6]}@x")
    pg_session.add(prof); pg_session.flush()

    turma = Turma(
        escola_id=escola.id, codigo="T1", serie="2S",
        nome="T1", professor_id=prof.id,
    )
    pg_session.add(turma); pg_session.flush()

    aluno = AlunoTurma(turma_id=turma.id, nome="A", telefone=f"+55{uuid.uuid4().hex[:8]}")
    pg_session.add(aluno); pg_session.flush()

    missao = Missao(codigo=f"MX{uuid.uuid4().hex[:6]}", serie="2S",
                     oficina_numero=13, titulo="x", modo_correcao="completo")
    pg_session.add(missao); pg_session.flush()

    ativ = Atividade(
        turma_id=turma.id, missao_id=missao.id,
        data_inicio=datetime.now(timezone.utc) - timedelta(days=1),
        data_fim=datetime.now(timezone.utc) + timedelta(days=1),
        criada_por_professor_id=prof.id,
    )
    pg_session.add(ativ); pg_session.flush()

    md = JogoMinideck(tema=f"t{uuid.uuid4().hex[:6]}", nome_humano="X")
    pg_session.add(md); pg_session.flush()

    partida = PartidaJogo(
        atividade_id=ativ.id, minideck_id=md.id,
        grupo_codigo="Grupo Azul",
        cartas_escolhidas=["E01"],
        texto_montado="texto",
        prazo_reescrita=datetime.now(timezone.utc) + timedelta(days=2),
        criada_por_professor_id=prof.id,
    )
    pg_session.add(partida); pg_session.flush()

    r1 = ReescritaIndividual(
        partida_id=partida.id, aluno_turma_id=aluno.id, texto="v1",
    )
    pg_session.add(r1)
    pg_session.commit()

    r2 = ReescritaIndividual(
        partida_id=partida.id, aluno_turma_id=aluno.id, texto="v2",
    )
    pg_session.add(r2)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


@pytestmark_db
def test_multiplas_partidas_pra_mesma_atividade_passam(pg_session):
    """Decisão G.1.2: 1:N suportado. Inserir 2 partidas com mesma
    atividade_id mas grupo_codigo diferente passa. Inserir 2 com
    mesmo grupo_codigo bate UNIQUE."""
    from sqlalchemy.exc import IntegrityError
    from redato_backend.portal.models import (
        Atividade, Escola, JogoMinideck, Missao, PartidaJogo,
        Professor, Turma,
    )

    escola = Escola(codigo=f"E{uuid.uuid4().hex[:6]}", nome="x",
                     estado="SP", municipio="x")
    pg_session.add(escola); pg_session.flush()

    prof = Professor(escola_id=escola.id, nome="P",
                      email=f"p2{uuid.uuid4().hex[:6]}@x")
    pg_session.add(prof); pg_session.flush()

    turma = Turma(escola_id=escola.id, codigo=f"T{uuid.uuid4().hex[:6]}",
                   serie="2S", nome="T2", professor_id=prof.id)
    pg_session.add(turma); pg_session.flush()

    missao = Missao(codigo=f"M2{uuid.uuid4().hex[:6]}", serie="2S",
                     oficina_numero=13, titulo="x", modo_correcao="completo")
    pg_session.add(missao); pg_session.flush()

    ativ = Atividade(
        turma_id=turma.id, missao_id=missao.id,
        data_inicio=datetime.now(timezone.utc) - timedelta(days=1),
        data_fim=datetime.now(timezone.utc) + timedelta(days=1),
        criada_por_professor_id=prof.id,
    )
    pg_session.add(ativ); pg_session.flush()

    md = JogoMinideck(tema=f"t2{uuid.uuid4().hex[:6]}", nome_humano="X")
    pg_session.add(md); pg_session.flush()

    p_azul = PartidaJogo(
        atividade_id=ativ.id, minideck_id=md.id,
        grupo_codigo="Grupo Azul",
        cartas_escolhidas=["E01"], texto_montado="x",
        prazo_reescrita=datetime.now(timezone.utc) + timedelta(days=2),
        criada_por_professor_id=prof.id,
    )
    p_verde = PartidaJogo(
        atividade_id=ativ.id, minideck_id=md.id,
        grupo_codigo="Grupo Verde",
        cartas_escolhidas=["E02"], texto_montado="x",
        prazo_reescrita=datetime.now(timezone.utc) + timedelta(days=2),
        criada_por_professor_id=prof.id,
    )
    pg_session.add_all([p_azul, p_verde])
    pg_session.commit()  # ambos OK

    # Segundo "Grupo Azul" na mesma atividade — viola UNIQUE
    p_dup = PartidaJogo(
        atividade_id=ativ.id, minideck_id=md.id,
        grupo_codigo="Grupo Azul",
        cartas_escolhidas=["E03"], texto_montado="x",
        prazo_reescrita=datetime.now(timezone.utc) + timedelta(days=2),
        criada_por_professor_id=prof.id,
    )
    pg_session.add(p_dup)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()


@pytestmark_db
def test_unique_minideck_codigo_em_lacuna(pg_session):
    """`P01` pode existir em vários temas, mas não 2x no mesmo tema.
    Garante que a UNIQUE composta é (minideck_id, codigo)."""
    from sqlalchemy.exc import IntegrityError
    from redato_backend.portal.models import CartaLacuna, JogoMinideck

    md1 = JogoMinideck(tema=f"a{uuid.uuid4().hex[:6]}", nome_humano="A")
    md2 = JogoMinideck(tema=f"b{uuid.uuid4().hex[:6]}", nome_humano="B")
    pg_session.add_all([md1, md2])
    pg_session.flush()

    # Mesmo codigo em temas diferentes — passa
    c1 = CartaLacuna(minideck_id=md1.id, tipo="PROBLEMA",
                      codigo="P01", conteudo="cont1")
    c2 = CartaLacuna(minideck_id=md2.id, tipo="PROBLEMA",
                      codigo="P01", conteudo="cont2")
    pg_session.add_all([c1, c2])
    pg_session.commit()

    # Mesmo codigo no mesmo tema — bate UNIQUE
    c_dup = CartaLacuna(minideck_id=md1.id, tipo="REPERTORIO",
                         codigo="P01", conteudo="cont3")
    pg_session.add(c_dup)
    with pytest.raises(IntegrityError):
        pg_session.commit()
    pg_session.rollback()
