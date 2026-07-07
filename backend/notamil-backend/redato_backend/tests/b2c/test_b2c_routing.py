"""Roteamento e FSM do B2C (SPEC_B2C_REDATO.md §7 critérios 1-3, 6, 8-9).

Sem Postgres: `repo` é o FakeStore (conftest), OCR/grader/Asaas são
fakes. Exercita `maybe_route_b2c`, que é o ponto que o bot chama.
"""
from __future__ import annotations

import pytest

from redato_backend.b2c.router import maybe_route_b2c
from redato_backend.b2c import messages as M


def _msg(phone="+5511999990000", text=None, image_path=None):
    from redato_backend.whatsapp.bot import InboundMessage
    return InboundMessage(phone=phone, text=text, image_path=image_path)


# ──────────────────────────────────────────────────────────────────────
# Critério 8 — flag off → comportamento atual intacto
# ──────────────────────────────────────────────────────────────────────

def test_flag_off_retorna_none(monkeypatch, store):
    """Sem REDATO_B2C_ENABLED, o desvio nem toca o repo — retorna None
    e o bot segue pro fluxo escola."""
    monkeypatch.delenv("REDATO_B2C_ENABLED", raising=False)
    store.add_parceiro(slug="demo", codigo_entrada="DEMO")
    assert maybe_route_b2c(_msg(text="QUERO DEMO")) is None


# ──────────────────────────────────────────────────────────────────────
# Critério 1 — telefone B2G não é sequestrado pelo B2C
# ──────────────────────────────────────────────────────────────────────

def test_telefone_b2g_nao_capturado(monkeypatch, store, b2c_on):
    store.add_parceiro(slug="demo", codigo_entrada="DEMO")
    from redato_backend.b2c import router as R
    # tem vínculo de turma → B2C devolve None mesmo com código no texto
    monkeypatch.setattr(R, "_tem_vinculo_b2g", lambda phone: True)
    monkeypatch.setattr(R, "_tem_estado_b2g", lambda phone: False)
    assert maybe_route_b2c(_msg(text="QUERO DEMO")) is None


def test_telefone_em_onboarding_b2g_nao_capturado(monkeypatch, store, b2c_on):
    store.add_parceiro(slug="demo", codigo_entrada="DEMO")
    from redato_backend.b2c import router as R
    monkeypatch.setattr(R, "_tem_vinculo_b2g", lambda phone: False)
    monkeypatch.setattr(R, "_tem_estado_b2g", lambda phone: True)  # SQLite state
    assert maybe_route_b2c(_msg(text="QUERO DEMO")) is None


# ──────────────────────────────────────────────────────────────────────
# Critério 2 — telefone novo + "QUERO DEMO" → cria AlunoB2C + M1
# ──────────────────────────────────────────────────────────────────────

def test_novo_com_codigo_cria_aluno_e_M1(store, b2c_on, sem_b2g):
    p = store.add_parceiro(slug="luma", codigo_entrada="LUMA",
                           nome_publico="Correção Luma",
                           nome_professor="Luma")
    replies = maybe_route_b2c(_msg(phone="+5511888887777", text="QUERO LUMA"))
    assert replies is not None and len(replies) == 1
    assert "Correção Luma" in replies[0].text
    aluno = store.get_aluno_por_telefone("+5511888887777")
    assert aluno is not None
    assert aluno.parceiro_id == p.id
    assert aluno.estado == "aguardando_nome"


def test_codigo_desconhecido_sem_captura(store, b2c_on, sem_b2g):
    store.add_parceiro(slug="demo", codigo_entrada="DEMO")
    # linha compartilhada (default): sem código válido → None
    assert maybe_route_b2c(_msg(text="oi tudo bem")) is None


def test_onboarding_nome_leva_a_degustacao(store, b2c_on, sem_b2g):
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="aguardando_nome")
    replies = maybe_route_b2c(_msg(phone="+5511777", text="Maria Silva"))
    aluno = store.get_aluno_por_telefone("+5511777")
    assert aluno.nome == "Maria Silva"
    assert aluno.estado == "degustacao"
    assert aluno.consent_lgpd_at is not None       # continuar = aceite LGPD
    assert "Maria" in replies[0].text


# ──────────────────────────────────────────────────────────────────────
# Critério 3 — degustação: 1 grátis corrige; 2ª sem pagar → M4, não corrige
# ──────────────────────────────────────────────────────────────────────

def test_degustacao_corrige_uma_e_depois_paywall(
    store, b2c_on, sem_b2g, fake_correcao, mock_asaas,
):
    p = store.add_parceiro(preco_centavos=3990, wallet_id_asaas="w_1",
                           share_pct=30)
    a = store.add_aluno("+5511777", p.id, estado="degustacao", nome="Maria")

    # 1ª foto → corrige (M3) + já dispara paywall (M4)
    replies = maybe_route_b2c(_msg(phone="+5511777", image_path="/tmp/f.jpg"))
    textos = " ".join(r.text for r in replies)
    assert "880/1000" in textos
    assert "assinatura" in textos.lower()
    assert store.get_aluno_por_telefone("+5511777").estado == "aguardando_pagamento"
    assert len([e for e in store.envios if e["aluno_id"] == a.id]) == 1

    # 2ª foto sem pagar → só paywall, NÃO corrige (nenhum envio novo)
    replies2 = maybe_route_b2c(_msg(phone="+5511777", image_path="/tmp/f2.jpg"))
    assert all("880/1000" not in r.text for r in replies2)
    assert "assinatura" in " ".join(r.text for r in replies2).lower()
    assert len([e for e in store.envios if e["aluno_id"] == a.id]) == 1


def test_foto_ilegivel_na_degustacao(store, b2c_on, sem_b2g, monkeypatch):
    from redato_backend.b2c import correction as C

    class _Ocr:
        text = ""
        rejected = True
        quality_issues = ["foto_escura"]

    monkeypatch.setattr(C, "transcrever", lambda p: _Ocr())
    p = store.add_parceiro()
    store.add_aluno("+5511777", p.id, estado="degustacao", nome="Maria")
    replies = maybe_route_b2c(_msg(phone="+5511777", image_path="/tmp/f.jpg"))
    assert "ler bem" in replies[0].text
    assert not store.envios


# ──────────────────────────────────────────────────────────────────────
# Critério 6 — fair use: 11ª correção do dia → M7
# ──────────────────────────────────────────────────────────────────────

def test_fair_use_bloqueia_11a(store, b2c_on, sem_b2g, fake_correcao):
    p = store.add_parceiro()
    a = store.add_aluno("+5511777", p.id, estado="ativo", nome="Maria")
    for _ in range(10):
        store.registrar_envio(a.id, p.id, nota_total=800)
    replies = maybe_route_b2c(_msg(phone="+5511777", image_path="/tmp/f.jpg"))
    assert "amanhã" in replies[0].text.lower()
    # não gravou 11º envio
    assert len([e for e in store.envios if e["aluno_id"] == a.id]) == 10


def test_ativo_corrige_e_entrega_M6(store, b2c_on, sem_b2g, fake_correcao):
    p = store.add_parceiro()
    a = store.add_aluno("+5511777", p.id, estado="ativo", nome="Maria")
    store.registrar_envio(a.id, p.id, nota_total=800)  # histórico p/ evolução
    replies = maybe_route_b2c(_msg(phone="+5511777", image_path="/tmp/f.jpg"))
    txt = replies[0].text
    assert "880/1000" in txt
    assert "evolução" in txt.lower()
    assert len([e for e in store.envios if e["aluno_id"] == a.id]) == 2


# ──────────────────────────────────────────────────────────────────────
# Critério 9 — nenhuma mensagem expõe % de share ou termos comerciais
# ──────────────────────────────────────────────────────────────────────

def test_copies_nao_vazam_dado_comercial():
    proibidos = ("%", "share", "split", "walletId", "wallet", "percentual",
                 "repasse", "comissão", "comissao")
    copies = [v for k, v in vars(M).items()
              if k.isupper() and isinstance(v, str)]
    assert copies, "esperava constantes de mensagem"
    for texto in copies:
        low = texto.lower()
        for termo in proibidos:
            assert termo.lower() not in low, f"'{termo}' vazou em: {texto!r}"
