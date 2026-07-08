"""Janela de 24h do WhatsApp (ADENDO §D9) — critério de aceite 17."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from redato_backend.b2c.notify import enviar_negocio


class _SpySender:
    def __init__(self):
        self.freeform_calls = []
        self.template_calls = []

    def freeform(self, phone, texto):
        self.freeform_calls.append((phone, texto))

    def template(self, phone, content_sid, variables):
        self.template_calls.append((phone, content_sid, variables))


_AGORA = datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)


def test_dentro_da_janela_usa_freeform():
    spy = _SpySender()
    caminho = enviar_negocio(
        "+5511777", "oi", template_key="M8",
        valores={"nome": "A", "nome_publico": "B", "link_fatura": "L"},
        ultima_inbound_at=_AGORA - timedelta(hours=2), agora=_AGORA, sender=spy,
    )
    assert caminho == "freeform"
    assert spy.freeform_calls and not spy.template_calls


def test_fora_da_janela_com_template_usa_content_sid(monkeypatch):
    monkeypatch.setenv("TWILIO_CONTENT_SID_M8", "HXcontent123")
    spy = _SpySender()
    caminho = enviar_negocio(
        "+5511777", "oi", template_key="M8",
        valores={"nome": "Ana", "nome_publico": "Luma", "link_fatura": "link"},
        ultima_inbound_at=_AGORA - timedelta(hours=30), agora=_AGORA, sender=spy,
    )
    assert caminho == "content_sid"
    # ContentVariables posicional montado pela ORDEM da spec (M8).
    assert spy.template_calls == [
        ("+5511777", "HXcontent123", {"1": "Ana", "2": "Luma", "3": "link"})]
    assert not spy.freeform_calls


def test_fora_da_janela_sem_template_degrada_freeform(monkeypatch):
    monkeypatch.delenv("TWILIO_CONTENT_SID_M8", raising=False)
    spy = _SpySender()
    caminho = enviar_negocio(
        "+5511777", "oi", template_key="M8",
        valores={"nome": "A", "nome_publico": "B", "link_fatura": "L"},
        ultima_inbound_at=_AGORA - timedelta(hours=30), agora=_AGORA, sender=spy,
    )
    assert caminho == "freeform_fallback"
    assert spy.freeform_calls and not spy.template_calls


def test_sem_ultima_inbound_trata_como_fora_da_janela(monkeypatch):
    monkeypatch.setenv("TWILIO_CONTENT_SID_M5", "HXm5")
    spy = _SpySender()
    caminho = enviar_negocio(
        "+5511777", "oi", template_key="M5",
        valores={"nome": "x", "nome_publico": "y"},
        ultima_inbound_at=None, agora=_AGORA, sender=spy,
    )
    assert caminho == "content_sid"
