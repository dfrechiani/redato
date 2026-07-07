"""Envio de mensagens B2C com respeito à janela de 24h (ADENDO §D9).

M5/M8/M9 são iniciadas pelo negócio e podem cair FORA da janela de 24h
desde a última mensagem do aluno — aí o Twilio só entrega template
pré-aprovado (Content API); freeform falha em silêncio.

`enviar_negocio` decide: dentro da janela → freeform; fora → template
com Content SID (env `TWILIO_CONTENT_SID_{M5|M8|M9}`). Retorna o caminho
usado (`freeform` | `content_sid` | `freeform_fallback`) — o MVP/teste
usa um `sender` mock que registra o caminho.

M3/M6/M16 são sempre resposta imediata (dentro da janela) — não passam
por aqui, vão como reply normal do bot.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List, Optional


logger = logging.getLogger(__name__)

_JANELA = timedelta(hours=24)


class TwilioSender:
    """Sender de produção. `template` usa Content API se o provider expõe
    `send_template`; senão degrada pra freeform (com aviso)."""

    def freeform(self, phone: str, texto: str) -> None:
        from redato_backend.whatsapp import twilio_provider as TW
        TW.send_replies(phone, [texto])

    def template(self, phone: str, content_sid: str,
                 variables: List[str]) -> None:
        from redato_backend.whatsapp import twilio_provider as TW
        fn = getattr(TW, "send_template", None)
        if fn is not None:
            fn(phone, content_sid, variables)
        else:  # provider ainda sem suporte a template — não perder a msg
            logger.warning(
                "twilio_provider sem send_template; degradando content_sid "
                "%s pra freeform", content_sid,
            )
            TW.send_replies(phone, [f"[{content_sid}] " + " · ".join(variables)])


def enviar_negocio(
    telefone: str,
    texto: str,
    *,
    template_key: Optional[str] = None,
    template_vars: Optional[List[str]] = None,
    ultima_inbound_at: Optional[datetime] = None,
    agora: Optional[datetime] = None,
    sender: Optional[Any] = None,
) -> str:
    """Envia uma mensagem iniciada pelo negócio respeitando a janela 24h.
    Retorna o caminho usado."""
    sender = sender or TwilioSender()
    agora = agora or datetime.now(timezone.utc)
    dentro = (
        ultima_inbound_at is not None
        and (agora - ultima_inbound_at) < _JANELA
    )
    if dentro:
        sender.freeform(telefone, texto)
        return "freeform"

    sid = os.getenv(f"TWILIO_CONTENT_SID_{template_key}") if template_key else None
    if sid:
        sender.template(telefone, sid, template_vars or [])
        return "content_sid"

    # Fora da janela e sem template aprovado (gate do Daniel, §15). Não
    # some a mensagem: tenta freeform (pode falhar no Twilio) + loga.
    logger.warning(
        "B2C: mensagem de negócio fora da janela 24h e sem "
        "TWILIO_CONTENT_SID_%s — freeform degradado (submeter template).",
        template_key,
    )
    sender.freeform(telefone, texto)
    return "freeform_fallback"


def notificar_negocio(
    telefone: str,
    texto: str,
    *,
    template_key: str,
    template_vars: List[str],
    ultima_inbound_at: Optional[datetime],
    override: Optional[Callable[[str, List[str]], None]] = None,
) -> str:
    """Ponto usado por webhook/tick. `override` (testes) captura o texto
    sem tocar Twilio; em produção (override=None) roda a janela 24h."""
    if override is not None:
        override(telefone, [texto])
        return "override"
    return enviar_negocio(
        telefone, texto, template_key=template_key,
        template_vars=template_vars, ultima_inbound_at=ultima_inbound_at,
    )
