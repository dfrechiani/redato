"""Testes do helper de mensagens pós-correção pra reavaliação (M9.6).

Bug que motivou (2026-04-29): aluno escolhia "2 — reavaliar como nova
tentativa", bot processava nova correção, mas a UI ficava idêntica à
1ª tentativa — aluno não sabia se a nova versão tinha realmente entrado
no sistema. Pior: o INSERT em Postgres falhava silenciosamente
(`uq_envio_atividade_aluno`), aí o feedback exibido era da tentativa
ANTIGA, não da nova.

Fix M9.6:
1. Constraint UNIQUE inclui `tentativa_n` (migration g0a1b2c3d4e5).
2. Falha em Postgres vira ERROR + raise (não mais warning silencioso).
3. Bot adiciona "📬 Tentativa N registrada. Avaliando sua nova versão..."
   ANTES do feedback quando reavaliação foi pra Postgres com sucesso.

Estes testes cobrem a regra (3) — `_build_messages_pos_correcao`. As
regras (1) e (2) são cobertas no integration de portal_link + migration
roundtrip.
"""
from __future__ import annotations


# ──────────────────────────────────────────────────────────────────────
# Caminho feliz — tentativa N >= 2 com Postgres OK
# ──────────────────────────────────────────────────────────────────────

def test_reavaliacao_com_postgres_ok_emite_ack_e_feedback():
    """Caso real do bug: aluno escolhe opção 2, Postgres salva
    tentativa 2 com sucesso. UI deve emitir 2 mensagens — ack curto
    com número da tentativa, depois feedback."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao

    msgs = _build_messages_pos_correcao(
        resposta="Sua redação tirou 800. Pontos fortes: ...",
        skip_duplicate_check=True,
        postgres_falhou=False,
        tentativa_n=2,
    )

    assert len(msgs) == 2
    assert "Tentativa 2 registrada" in msgs[0].text
    assert "Avaliando sua nova versão" in msgs[0].text
    # Feedback vem em segundo
    assert "Sua redação tirou 800" in msgs[1].text


def test_reavaliacao_3a_tentativa_mostra_numero_correto():
    """Aluno na 3ª tentativa — ack deve dizer 'Tentativa 3', não 2."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao

    msgs = _build_messages_pos_correcao(
        resposta="Feedback tentativa 3.",
        skip_duplicate_check=True,
        postgres_falhou=False,
        tentativa_n=3,
    )
    assert len(msgs) == 2
    assert "Tentativa 3 registrada" in msgs[0].text


# ──────────────────────────────────────────────────────────────────────
# Cenários onde NÃO mostra o ack
# ──────────────────────────────────────────────────────────────────────

def test_primeira_tentativa_nao_mostra_ack():
    """Aluno enviando 1ª vez (skip_duplicate_check=False, tentativa_n=1).
    Sem ack — só feedback. Adicionar texto extra na 1ª seria ruído."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao

    msgs = _build_messages_pos_correcao(
        resposta="Primeira correção. Nota: 720.",
        skip_duplicate_check=False,
        postgres_falhou=False,
        tentativa_n=1,
    )
    assert len(msgs) == 1
    assert "Tentativa" not in msgs[0].text
    assert "Primeira correção" in msgs[0].text


def test_reavaliacao_mas_postgres_falhou_nao_mostra_numero_inconsistente():
    """Defensiva crítica: se Postgres falhou, o `tentativa_n` retornado
    pode estar errado (default=1 mesmo sendo 3ª tentativa real). Não
    mostrar o número errado pro aluno — só feedback. Daniel já vê o
    ERROR no Railway pra investigar."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao

    msgs = _build_messages_pos_correcao(
        resposta="Feedback da nova versão.",
        skip_duplicate_check=True,
        postgres_falhou=True,
        tentativa_n=1,  # default quando falha
    )
    assert len(msgs) == 1
    assert "Tentativa" not in msgs[0].text


def test_skip_duplicate_check_mas_tentativa_1_nao_mostra():
    """Caso degenerado: skip_duplicate_check=True mas tentativa_n=1.
    Não deveria acontecer em prod (skip implica reavaliação = >=2),
    mas se acontecer não mostra o ack — '1' não comunica nada útil."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao

    msgs = _build_messages_pos_correcao(
        resposta="Feedback.",
        skip_duplicate_check=True,
        postgres_falhou=False,
        tentativa_n=1,
    )
    assert len(msgs) == 1


# ──────────────────────────────────────────────────────────────────────
# Estrutura das mensagens (formato)
# ──────────────────────────────────────────────────────────────────────

def test_ack_e_feedback_sao_outbound_messages():
    """Sanity: o helper retorna List[OutboundMessage] — não strings nem
    tuples. Caller `_process_photo` retorna isso direto pro webhook
    Twilio que serializa como TwiML."""
    from redato_backend.whatsapp.bot import (
        _build_messages_pos_correcao, OutboundMessage,
    )
    msgs = _build_messages_pos_correcao(
        resposta="x", skip_duplicate_check=True,
        postgres_falhou=False, tentativa_n=2,
    )
    assert all(isinstance(m, OutboundMessage) for m in msgs)


def test_ack_message_inclui_emoji_de_envelope():
    """UX: ack começa com 📬 pra distinguir visualmente do feedback que
    pode ser longo. WhatsApp formata negrito *…* corretamente."""
    from redato_backend.whatsapp.bot import _build_messages_pos_correcao
    msgs = _build_messages_pos_correcao(
        resposta="x", skip_duplicate_check=True,
        postgres_falhou=False, tentativa_n=2,
    )
    assert "📬" in msgs[0].text
    assert "*Tentativa 2 registrada.*" in msgs[0].text
