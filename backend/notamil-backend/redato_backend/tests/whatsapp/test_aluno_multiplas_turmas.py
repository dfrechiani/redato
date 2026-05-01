"""Testes da desambiguação de turma quando aluno está em 2+ vínculos
ativos no portal (`alunos_turma`).

Caso real (30/04/2026, +556196668856): aluno em turmas 1A (1S) e 2A
(2S). Bot escolhia arbitrariamente uma turma e quando OF14 não existia
nessa, dava "atividade não encontrada". Workaround: desativar vínculo
manualmente. Fix nesse arquivo cobre:

1. Aluno em 1 vínculo → comportamento atual (sem regressão)
2. Aluno em 2+ vínculos sem turma persistida → bot pergunta
3. Aluno escolhe número válido → bot persiste em `alunos.turma_ativa_id`
4. Aluno responde inválido (texto/número fora) → bot pede de novo
5. Aluno manda foto durante AWAITING_TURMA_CHOICE → guard-rail (não
   processa silenciosamente, reenvia pergunta)
6. Comando "trocar turma" → limpa persistido + abre nova escolha
7. "trocar turma" com 1 vínculo só → bot informa que não dá
8. Próxima foto dentro do TTL (2h) → atalha sem perguntar
9. Turma persistida não está mais ativa → limpa e pergunta de novo

Também cobre helpers de `persistence.py`: set/get/clear com TTL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional
from unittest.mock import MagicMock

import pytest


# ──────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────

PHONE = "+5561999999999"
TURMA_1A = "uuid-turma-1a"
TURMA_2A = "uuid-turma-2a"


class _Vinculo:
    """Mimica `portal_link.AlunoVinculo` — só os campos consumidos
    pelos handlers que estamos testando."""
    def __init__(self, turma_id: str, turma_codigo: str, escola_nome: str,
                 aluno_turma_id: str = "uuid-aluno-turma-x",
                 nome: str = "Aluno Teste"):
        self.aluno_turma_id = aluno_turma_id
        self.nome = nome
        self.telefone = PHONE
        self.turma_id = turma_id
        self.turma_codigo = turma_codigo
        self.escola_nome = escola_nome


def _v(n: int) -> _Vinculo:
    if n == 1:
        return _Vinculo(TURMA_1A, "TURMA-1A-2026", "EM Vital Brazil")
    return _Vinculo(TURMA_2A, "TURMA-2A-2026", "EM Vital Brazil")


@pytest.fixture(autouse=True)
def isolar_sqlite_fsm(monkeypatch, tmp_path):
    """Cada teste tem seu SQLite (mesmo padrão de test_bot_jogo_partida)."""
    db_path = tmp_path / "test_redato.db"
    monkeypatch.setenv("REDATO_WHATSAPP_DB", str(db_path))


@pytest.fixture
def aluno_em_ready():
    """Cria aluno em estado READY no SQLite local pré-test."""
    from redato_backend.whatsapp import persistence as P
    P.init_db()
    P.upsert_aluno(PHONE, nome="Aluno Teste", estado="READY")
    yield
    # cleanup automático via tmp_path


# ──────────────────────────────────────────────────────────────────────
# Persistência — set/get/clear com TTL
# ──────────────────────────────────────────────────────────────────────

def test_set_turma_ativa_persiste_e_recupera(aluno_em_ready):
    from redato_backend.whatsapp import persistence as P
    P.set_turma_ativa(PHONE, TURMA_1A)
    assert P.get_turma_ativa(PHONE) == TURMA_1A


def test_get_turma_ativa_sem_escolha_retorna_none(aluno_em_ready):
    from redato_backend.whatsapp import persistence as P
    assert P.get_turma_ativa(PHONE) is None


def test_get_turma_ativa_expirado_retorna_none(aluno_em_ready):
    """TTL de 2h — escolha de 3h atrás expira."""
    from redato_backend.whatsapp import persistence as P
    P.set_turma_ativa(PHONE, TURMA_1A)
    # Manipula timestamp pra 3h atrás
    velho = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    with P._conn() as c:
        c.execute(
            "UPDATE alunos SET turma_ativa_em = ? WHERE phone = ?",
            (velho, PHONE),
        )
    assert P.get_turma_ativa(PHONE) is None


def test_clear_turma_ativa_zera(aluno_em_ready):
    from redato_backend.whatsapp import persistence as P
    P.set_turma_ativa(PHONE, TURMA_1A)
    assert P.get_turma_ativa(PHONE) == TURMA_1A
    P.clear_turma_ativa(PHONE)
    assert P.get_turma_ativa(PHONE) is None


def test_get_turma_ativa_aluno_inexistente_retorna_none():
    from redato_backend.whatsapp import persistence as P
    P.init_db()
    assert P.get_turma_ativa("+5500000000000") is None


# ──────────────────────────────────────────────────────────────────────
# _handle_trocar_turma
# ──────────────────────────────────────────────────────────────────────

def test_trocar_turma_com_2_vinculos_pergunta(monkeypatch, aluno_em_ready):
    """Aluno com 2+ vínculos manda 'trocar turma' → bot lista turmas
    e seta AWAITING_TURMA_CHOICE."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1), _v(2)],
    )
    P.set_turma_ativa(PHONE, TURMA_1A)  # já tinha escolhido antes

    msg = bot.InboundMessage(phone=PHONE, text="trocar turma")
    out = bot.handle_inbound(msg)

    assert len(out) == 1
    assert "vamos trocar" in out[0].text.lower() or "trocar de turma" in out[0].text.lower()
    assert "TURMA-1A" in out[0].text
    assert "TURMA-2A" in out[0].text

    # turma_ativa foi limpa
    assert P.get_turma_ativa(PHONE) is None
    # estado é AWAITING_TURMA_CHOICE (sem barra — sem foto pendente)
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"] == bot.AWAITING_TURMA_CHOICE


def test_trocar_turma_com_1_vinculo_responde_unica(monkeypatch, aluno_em_ready):
    """Aluno tem só 1 turma → 'trocar turma' responde que não dá."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1)],
    )

    msg = bot.InboundMessage(phone=PHONE, text="trocar turma")
    out = bot.handle_inbound(msg)
    assert len(out) == 1
    assert "1 turma" in out[0].text or "só tem 1" in out[0].text

    # estado preservado
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"] == "READY"


def test_trocar_turma_aceita_variacoes(monkeypatch, aluno_em_ready):
    """'trocar turma', 'mudar turma', 'trocar de turma' devem disparar."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1), _v(2)],
    )

    for cmd in ["trocar turma", "Trocar Turma", "mudar turma",
                "trocar de turma", "outra turma"]:
        # reset estado pra READY entre iterações
        P.upsert_aluno(PHONE, estado="READY")
        msg = bot.InboundMessage(phone=PHONE, text=cmd)
        out = bot.handle_inbound(msg)
        assert len(out) == 1
        assert ("trocar" in out[0].text.lower()
                or "TURMA-1A" in out[0].text), f"falhou pra '{cmd}'"


# ──────────────────────────────────────────────────────────────────────
# _handle_turma_choice — escolha + persistência + guard-rail
# ──────────────────────────────────────────────────────────────────────

def test_aluno_responde_numero_valido_persiste(monkeypatch, aluno_em_ready):
    """Aluno em AWAITING_TURMA_CHOICE responde '1' → set_turma_ativa
    chamado com turma_id correta + estado vai READY."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1), _v(2)],
    )
    # Estado AWAITING_TURMA_CHOICE sem foto/missão (vindo de "trocar turma")
    P.upsert_aluno(PHONE, estado=bot.AWAITING_TURMA_CHOICE)

    msg = bot.InboundMessage(phone=PHONE, text="1")
    out = bot.handle_inbound(msg)

    assert len(out) == 1
    assert "TURMA-1A" in out[0].text
    assert P.get_turma_ativa(PHONE) == TURMA_1A
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"] == "READY"


def test_aluno_responde_numero_fora_de_range(monkeypatch, aluno_em_ready):
    """Responde '5' mas só tem 2 turmas → mensagem de inválido."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1), _v(2)],
    )
    P.upsert_aluno(PHONE, estado=bot.AWAITING_TURMA_CHOICE)

    msg = bot.InboundMessage(phone=PHONE, text="5")
    out = bot.handle_inbound(msg)

    assert len(out) == 1
    assert "Não entendi" in out[0].text or "Responde" in out[0].text
    # Estado preserva AWAITING_TURMA_CHOICE
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"] == bot.AWAITING_TURMA_CHOICE
    # Turma_ativa NÃO setada
    assert P.get_turma_ativa(PHONE) is None


def test_aluno_responde_texto_invalido(monkeypatch, aluno_em_ready):
    """Responde 'oi' → mensagem de inválido. Estado preserva."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1), _v(2)],
    )
    P.upsert_aluno(PHONE, estado=bot.AWAITING_TURMA_CHOICE)

    msg = bot.InboundMessage(phone=PHONE, text="oi")
    out = bot.handle_inbound(msg)
    assert len(out) == 1
    assert "Não entendi" in out[0].text or "número" in out[0].text.lower()


def test_foto_durante_escolha_guard_rail(monkeypatch, aluno_em_ready):
    """Aluno em AWAITING_TURMA_CHOICE manda FOTO em vez de responder
    o número → bot reenvia a pergunta + mantém estado."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1), _v(2)],
    )
    P.upsert_aluno(PHONE, estado=bot.AWAITING_TURMA_CHOICE)

    msg = bot.InboundMessage(
        phone=PHONE, text=None, image_path="/tmp/foto.jpg",
    )
    out = bot.handle_inbound(msg)

    assert len(out) == 1
    # Mensagem contém pergunta + lista de turmas
    assert "TURMA-1A" in out[0].text
    assert "TURMA-2A" in out[0].text
    # Estado preserva — não consumiu a foto silenciosamente
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"] == bot.AWAITING_TURMA_CHOICE
    assert P.get_turma_ativa(PHONE) is None


# ──────────────────────────────────────────────────────────────────────
# Atalho via turma_ativa (funcionalidade central — economiza pergunta)
# ──────────────────────────────────────────────────────────────────────

def _mock_atividade_e_ocr(monkeypatch):
    """Mocks compartilhados pra _process_photo passar do bloco de
    desambiguação até o early-return em OCR rejected."""
    from redato_backend.whatsapp import (
        bot, portal_link as PL, persistence as P,
    )
    monkeypatch.setattr(
        PL, "find_atividade_para_missao",
        lambda turma_id, missao_codigo: MagicMock(
            status="ativa", data_inicio=None, data_fim=None,
        ),
    )
    # bot.py importa transcribe_with_quality_check direto no namespace
    # — mockar no módulo bot pra interceptar a chamada `ocr =
    # transcribe_with_quality_check(...)`.
    monkeypatch.setattr(
        bot, "transcribe_with_quality_check",
        lambda image_path: MagicMock(
            rejected=True, quality_issues=["foto_borrada"],
            metrics=None, text=None,
        ),
    )
    # compute_image_hash lê arquivo real — mock pra qualquer string.
    monkeypatch.setattr(P, "compute_image_hash", lambda path: "fake_hash")


def test_atalho_quando_turma_ativa_bate_vinculo(monkeypatch, aluno_em_ready):
    """Aluno escolheu turma há 1h, manda foto nova: bot NÃO pergunta de
    novo (atalha). Verifica que turma_ativa permanece intacta após.

    Testa só o ramo "tem turma_ativa válida" via simulação direta de
    `_process_photo` (sem rodar OCR/grading reais — basta confirmar
    que o ramo de pergunta NÃO foi acionado)."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1), _v(2)],
    )
    _mock_atividade_e_ocr(monkeypatch)

    P.set_turma_ativa(PHONE, TURMA_1A)

    out = bot._process_photo(
        phone=PHONE, image_path="/tmp/foto.jpg",
        missao_canon="RJ1·OF14·MF",
        aluno=P.get_aluno(PHONE) or {},
    )

    # O ramo "len(vinculos) > 1" + "sem turma_ativa" teria setado
    # AWAITING_TURMA_CHOICE. Testamos que isso NÃO aconteceu.
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"] != bot.AWAITING_TURMA_CHOICE
    # turma_ativa permanece (não é limpa pelo atalho)
    assert P.get_turma_ativa(PHONE) == TURMA_1A


def test_turma_ativa_nao_bate_vinculo_limpa(monkeypatch, aluno_em_ready):
    """Aluno escolheu turma 1A, depois portal desativou esse vínculo.
    Próxima foto: turma_ativa não bate com nenhum vínculo, bot LIMPA
    e abre nova escolha."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    # Aluno escolheu turma 1A no passado
    P.set_turma_ativa(PHONE, TURMA_1A)

    # Agora só tem vínculo na 2A (e numa nova 3A)
    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(2), _Vinculo("uuid-3a", "TURMA-3A-2026", "Escola X")],
    )

    out = bot._process_photo(
        phone=PHONE, image_path="/tmp/foto.jpg",
        missao_canon="RJ1·OF14·MF",
        aluno=P.get_aluno(PHONE) or {},
    )

    # Bot pergunta de novo (turma 1A não bate com nenhum dos vínculos)
    assert len(out) == 1
    assert "TURMA-2A" in out[0].text
    assert "TURMA-3A" in out[0].text
    # turma_ativa (1A) foi limpa pq não bate
    assert P.get_turma_ativa(PHONE) is None
    # Estado seta AWAITING_TURMA_CHOICE com payload
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"].startswith(bot.AWAITING_TURMA_CHOICE + "|")


# ──────────────────────────────────────────────────────────────────────
# Aluno único vínculo — comportamento regresso preservado
# ──────────────────────────────────────────────────────────────────────

def test_aluno_unico_vinculo_nao_pergunta(monkeypatch, aluno_em_ready):
    """Aluno em 1 turma só → comportamento atual preservado (sem
    pergunta de turma)."""
    from redato_backend.whatsapp import bot, persistence as P, portal_link as PL

    monkeypatch.setattr(
        PL, "list_alunos_ativos_por_telefone",
        lambda phone: [_v(1)],
    )
    _mock_atividade_e_ocr(monkeypatch)

    out = bot._process_photo(
        phone=PHONE, image_path="/tmp/foto.jpg",
        missao_canon="RJ1·OF14·MF",
        aluno=P.get_aluno(PHONE) or {},
    )

    # Não pergunta turma — segue pra OCR
    aluno = P.get_aluno(PHONE)
    assert aluno["estado"] != bot.AWAITING_TURMA_CHOICE
