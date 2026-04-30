"""Testes de fragmentação de mensagens longas pro Twilio (hotfix
2026-04-29).

Bug original: Twilio recusa mensagens >1600 chars com HTTP 400. No
fluxo do jogo Redato, texto cooperativo das cartas chegava a ~2300
chars e o aluno ficava sem feedback. Cobertura:

- Texto curto (sem `\\n\\n`): 1 chunk único, sem prefixo
- Texto médio (cabe inteiro): 1 chunk único, sem prefixo
- Texto longo: múltiplos chunks com prefixo "(parte N de M)"
- Empacotamento greedy preserva ordem dos parágrafos
- Cada chunk respeita ceiling de 1500 chars
- Caso limite — parágrafo único > 1500: log warning + retorna
  parágrafo intacto (não corta)
- send_replies fragmenta antes de chamar send_text
- Pausa de 300ms entre envios consecutivos (incluindo entre chunks
  da mesma reply)

Cliente Twilio mockado — testes não tocam API real.
"""
from __future__ import annotations

import logging
from unittest.mock import MagicMock, call, patch

import pytest


# ──────────────────────────────────────────────────────────────────────
# split_by_paragraph
# ──────────────────────────────────────────────────────────────────────

def test_texto_curto_sem_paragrafo_retorna_um_chunk():
    """300 chars sem `\\n\\n` — 1 chunk só, sem alteração."""
    from redato_backend.whatsapp.twilio_provider import split_by_paragraph
    text = "a" * 300
    chunks = split_by_paragraph(text, max_chars=1500)
    assert chunks == [text]


def test_texto_medio_que_cabe_inteiro_retorna_um_chunk():
    """1200 chars em 3 parágrafos — cabem todos no mesmo chunk."""
    from redato_backend.whatsapp.twilio_provider import split_by_paragraph
    p1 = "x" * 400
    p2 = "y" * 400
    p3 = "z" * 396  # 400+400+396 + 4 (2 separadores \n\n) = 1200
    text = "\n\n".join([p1, p2, p3])
    assert len(text) == 1200
    chunks = split_by_paragraph(text, max_chars=1500)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_texto_longo_quebra_em_2_chunks_por_paragrafo():
    """6 parágrafos × ~400 chars = ~2400 chars total. Greedy empacota
    primeiros 3 (1200 chars) num chunk; próximos 3 em outro chunk."""
    from redato_backend.whatsapp.twilio_provider import split_by_paragraph
    paragrafos = [f"PAR{i}-" + ("x" * 395) for i in range(6)]
    text = "\n\n".join(paragrafos)
    assert len(text) > 1500
    chunks = split_by_paragraph(text, max_chars=1500)
    assert len(chunks) >= 2
    # Cada chunk respeita ceiling
    for c in chunks:
        assert len(c) <= 1500, f"chunk de {len(c)} chars excede 1500"
    # Ordem dos parágrafos preservada — junta tudo de volta deve dar
    # exatamente o texto original
    rejoined = "\n\n".join(chunks)
    assert rejoined == text


def test_texto_muito_longo_3_ou_mais_chunks_todos_dentro_ceiling():
    """10 parágrafos de ~400 chars = ~4000 chars total. Esperado 3+
    chunks. Verifica ceiling em cada um."""
    from redato_backend.whatsapp.twilio_provider import split_by_paragraph
    paragrafos = [f"P{i}-" + ("z" * 397) for i in range(10)]
    text = "\n\n".join(paragrafos)
    assert len(text) > 3000
    chunks = split_by_paragraph(text, max_chars=1500)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c) <= 1500
    # Ordem preservada
    assert "\n\n".join(chunks) == text


def test_paragrafo_unico_excede_ceiling_loga_warning_e_retorna_intacto(
    caplog,
):
    """Caso limite: parágrafo único de 2000 chars > 1500. Não corta —
    log warning + retorna intacto. Twilio vai recusar mas o erro fica
    explícito (vs. silenciar o problema com hard-split)."""
    from redato_backend.whatsapp.twilio_provider import split_by_paragraph
    paragrafo = "G" * 2000  # sem \n\n internos
    with caplog.at_level(logging.WARNING):
        chunks = split_by_paragraph(paragrafo, max_chars=1500)
    assert chunks == [paragrafo]
    # Warning explícito sobre o tamanho
    assert any(
        "excede ceiling" in rec.message.lower()
        or "2000" in rec.message
        for rec in caplog.records
    )


def test_paragrafo_unico_gigante_no_meio_separa_dos_demais(caplog):
    """Mix: 2 parágrafos normais + 1 gigante + 1 normal. O gigante
    deve ficar em chunk próprio (sem hard-split), e os outros não
    devem ser absorvidos junto com ele."""
    from redato_backend.whatsapp.twilio_provider import split_by_paragraph
    p_normal = "x" * 300
    p_gigante = "y" * 2000
    text = "\n\n".join([p_normal, p_normal, p_gigante, p_normal])
    with caplog.at_level(logging.WARNING):
        chunks = split_by_paragraph(text, max_chars=1500)
    # Pelo menos 2 chunks. Gigante NÃO foi cortado — aparece em pelo
    # menos um chunk com seu tamanho original.
    assert any(p_gigante in c for c in chunks)
    # Não houve hard-split — nenhum chunk começa/termina no meio do
    # gigante (todos os "y" 2000 estão num único chunk)
    chunk_com_gigante = next(c for c in chunks if p_gigante in c)
    assert chunk_com_gigante.count("y") == 2000


def test_split_preserva_ordem_dos_paragrafos():
    """Ordem dos parágrafos no output deve bater com input — greedy
    nunca reordena."""
    from redato_backend.whatsapp.twilio_provider import split_by_paragraph
    paragrafos = [f"PAR-{letra}-" + ("a" * 400)
                  for letra in "ABCDEFGHIJ"]
    text = "\n\n".join(paragrafos)
    chunks = split_by_paragraph(text, max_chars=1500)
    rejoined = "\n\n".join(chunks)
    assert rejoined == text
    # E os marcadores PAR-A, PAR-B, ... aparecem em ordem A→J
    indices = []
    for letra in "ABCDEFGHIJ":
        idx = rejoined.find(f"PAR-{letra}-")
        assert idx >= 0
        indices.append(idx)
    assert indices == sorted(indices)


# ──────────────────────────────────────────────────────────────────────
# format_chunked
# ──────────────────────────────────────────────────────────────────────

def test_format_chunked_unico_retorna_intacto():
    """1 chunk só → sem prefixo "(parte 1 de 1)" (ruído visual)."""
    from redato_backend.whatsapp.twilio_provider import format_chunked
    chunks = ["mensagem única"]
    assert format_chunked(chunks) == ["mensagem única"]


def test_format_chunked_multiplos_aplicam_prefixo_parentese():
    """3 chunks → "(parte 1 de 3)", "(parte 2 de 3)", "(parte 3 de 3)".
    Formato exato: parêntese, lowercase "parte", " de ", sem espaço
    em ninguém."""
    from redato_backend.whatsapp.twilio_provider import format_chunked
    chunks = ["A", "B", "C"]
    out = format_chunked(chunks)
    assert out[0].startswith("(parte 1 de 3)\n\n")
    assert out[0].endswith("\n\nA")
    assert out[1].startswith("(parte 2 de 3)\n\n")
    assert out[2].startswith("(parte 3 de 3)\n\n")
    # Não aceita variantes ("Parte 1/3", "parte 1/3", etc.)
    for o in out:
        assert "/" not in o.split("\n\n")[0]


def test_format_chunked_lista_vazia_retorna_vazia():
    """Defensivo: lista vazia (input degenerado)."""
    from redato_backend.whatsapp.twilio_provider import format_chunked
    assert format_chunked([]) == []


def test_format_chunked_2_chunks_total_correto():
    """O número total no prefixo bate com len(chunks) — não com
    algum hardcode."""
    from redato_backend.whatsapp.twilio_provider import format_chunked
    out = format_chunked(["x", "y"])
    assert out[0].startswith("(parte 1 de 2)")
    assert out[1].startswith("(parte 2 de 2)")


# ──────────────────────────────────────────────────────────────────────
# send_replies — integração de fragmentação + envio
# ──────────────────────────────────────────────────────────────────────

@patch("redato_backend.whatsapp.twilio_provider.time.sleep")
@patch("redato_backend.whatsapp.twilio_provider.send_text")
def test_send_replies_msg_curta_envia_uma_chamada(
    mock_send_text, mock_sleep,
):
    """Reply de 200 chars passa direto pra send_text. Sem fragmentação,
    sem pausa (i=0)."""
    from redato_backend.whatsapp.twilio_provider import send_replies
    mock_send_text.side_effect = ["SID1"]
    sids = send_replies("+5511999000111", ["mensagem curta"])
    assert sids == ["SID1"]
    assert mock_send_text.call_count == 1
    mock_send_text.assert_called_once_with(
        "+5511999000111", "mensagem curta",
    )
    # i==0 → sem sleep
    mock_sleep.assert_not_called()


@patch("redato_backend.whatsapp.twilio_provider.time.sleep")
@patch("redato_backend.whatsapp.twilio_provider.send_text")
def test_send_replies_msg_longa_e_fragmentada_em_chunks(
    mock_send_text, mock_sleep,
):
    """Reply >1500 chars com vários parágrafos é fragmentada antes do
    envio. Cada chunk vira 1 chamada send_text com prefixo."""
    from redato_backend.whatsapp.twilio_provider import send_replies
    paragrafos = [f"P{i}-" + ("x" * 397) for i in range(8)]
    text_longo = "\n\n".join(paragrafos)
    mock_send_text.side_effect = [f"SID{i}" for i in range(10)]

    sids = send_replies("+5511999000222", [text_longo])
    # Pelo menos 2 chamadas (texto > 1500)
    assert mock_send_text.call_count >= 2
    # Cada chamada começa com "(parte N de M)"
    for c in mock_send_text.call_args_list:
        body = c.args[1]
        assert body.startswith("(parte ")
        assert " de " in body.split("\n\n")[0]
        assert len(body) <= 1500 + 30  # ceiling + folga do prefixo


@patch("redato_backend.whatsapp.twilio_provider.time.sleep")
@patch("redato_backend.whatsapp.twilio_provider.send_text")
def test_send_replies_pausa_300ms_entre_envios_consecutivos(
    mock_send_text, mock_sleep,
):
    """Entre cada par de envios consecutivos, time.sleep(0.3) é
    chamado. NÃO é chamado antes do 1º."""
    from redato_backend.whatsapp.twilio_provider import send_replies
    mock_send_text.side_effect = ["S1", "S2", "S3"]
    send_replies("+5511", ["a", "b", "c"])
    # 3 envios → 2 sleeps (entre 1-2 e entre 2-3)
    assert mock_sleep.call_count == 2
    for c in mock_sleep.call_args_list:
        assert c.args[0] == 0.3


@patch("redato_backend.whatsapp.twilio_provider.time.sleep")
@patch("redato_backend.whatsapp.twilio_provider.send_text")
def test_send_replies_pausa_entre_chunks_da_mesma_reply(
    mock_send_text, mock_sleep,
):
    """Quando UMA reply é fragmentada em N chunks, ainda há pausa de
    300ms entre cada um (preserva ordem no WhatsApp)."""
    from redato_backend.whatsapp.twilio_provider import send_replies
    paragrafos = [f"P{i}-" + ("x" * 397) for i in range(6)]
    text_longo = "\n\n".join(paragrafos)
    mock_send_text.side_effect = [f"S{i}" for i in range(10)]

    send_replies("+5511", [text_longo])
    # N chunks → N-1 sleeps. Verificamos só que houve pelo menos 1
    # sleep (caso de fragmentar 1 reply em 2+ chunks).
    assert mock_sleep.call_count >= 1


@patch("redato_backend.whatsapp.twilio_provider.time.sleep")
@patch("redato_backend.whatsapp.twilio_provider.send_text")
def test_send_replies_mix_curtas_e_longas_envia_tudo_em_ordem(
    mock_send_text, mock_sleep,
):
    """1ª reply curta + 2ª reply longa fragmentada + 3ª reply curta.
    Ordem de envio preservada: curta → chunks longos em ordem → curta."""
    from redato_backend.whatsapp.twilio_provider import send_replies
    paragrafos = [f"P{i}-" + ("x" * 397) for i in range(5)]
    text_longo = "\n\n".join(paragrafos)
    mock_send_text.side_effect = [f"S{i}" for i in range(10)]

    send_replies("+5511", [
        "curta antes",
        text_longo,
        "curta depois",
    ])
    bodies = [c.args[1] for c in mock_send_text.call_args_list]
    assert bodies[0] == "curta antes"
    assert bodies[-1] == "curta depois"
    # Os bodies do meio são chunks com prefixo
    for i in range(1, len(bodies) - 1):
        assert bodies[i].startswith("(parte ")


# ──────────────────────────────────────────────────────────────────────
# Cenário do bug original (smoke do hotfix)
# ──────────────────────────────────────────────────────────────────────

@patch("redato_backend.whatsapp.twilio_provider.time.sleep")
@patch("redato_backend.whatsapp.twilio_provider.send_text")
def test_cenario_bug_original_jogo_redato_2300_chars(
    mock_send_text, mock_sleep,
):
    """Reproduz o cenário que quebrou em prod: texto cooperativo do
    jogo Redato com ~2300 chars em 10 parágrafos. Antes do hotfix:
    Twilio devolvia HTTP 400. Depois: fragmenta em 2+ chunks e envia."""
    from redato_backend.whatsapp.twilio_provider import send_replies
    # Texto realístico — 10 parágrafos de ~230 chars cada
    paragrafos = [
        f"Parágrafo {i+1} expandido com cartas do grupo. " + ("texto " * 30)
        for i in range(10)
    ]
    texto_cooperativo = "\n\n".join(paragrafos)
    assert len(texto_cooperativo) > 1600  # bate o limite Twilio

    mock_send_text.side_effect = [f"S{i}" for i in range(10)]
    sids = send_replies("+5511999000333", [texto_cooperativo])
    assert len(sids) >= 2  # fragmentado
    # Nenhum chunk excede ceiling
    for c in mock_send_text.call_args_list:
        body = c.args[1]
        assert len(body) <= 1500 + 30
