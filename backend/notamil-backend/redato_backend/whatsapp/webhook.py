"""FastAPI router pro webhook Twilio.

Endpoint principal: `POST /twilio/webhook`. Recebe form-encoded body do
Twilio com mensagens recebidas (texto + foto). Roteia pra
`bot.handle_inbound` e responde via Twilio REST API (não TwiML inline,
porque algumas respostas podem demorar mais que a janela do TwiML).

Comportamento:
1. Valida assinatura X-Twilio-Signature (a menos que
   `TWILIO_VALIDATE_SIGNATURE=0` no dev local).
2. Devolve HTTP 200 imediatamente pro Twilio (evita retry).
3. Processa mensagem de forma síncrona (Fase A; Fase B usar background
   queue).
4. Envia respostas via REST API.
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict

from fastapi import APIRouter, Form, HTTPException, Request, Response

from redato_backend.whatsapp import twilio_provider as TW
from redato_backend.whatsapp.bot import handle_inbound


logger = logging.getLogger(__name__)
router = APIRouter()


def _process_in_background(form_dict: Dict[str, Any]) -> None:
    """Roda o pipeline em thread separada pra liberar a resposta HTTP
    do Twilio rápido (evita timeout de 15s do webhook)."""
    try:
        inbound = TW.parse_inbound(form_dict)
        logger.info("Inbound: phone=%s text=%r image=%s",
                    inbound.phone,
                    (inbound.text or "")[:80],
                    bool(inbound.image_path))
        replies = handle_inbound(inbound)
        if not replies:
            return
        TW.send_replies(inbound.phone,
                        [r.text for r in replies])
        logger.info("Sent %d replies to %s", len(replies), inbound.phone)
    except Exception:  # noqa: BLE001
        logger.exception("Erro processando webhook")


@router.post("/twilio/webhook")
async def twilio_webhook(request: Request) -> Response:
    """Recebe payload do Twilio. Valida assinatura, dispara processamento
    em background, retorna 200 vazio."""
    form = await request.form()
    form_dict: Dict[str, Any] = dict(form)

    # Validação de assinatura (opcional via env pra dev local com ngrok)
    if os.getenv("TWILIO_VALIDATE_SIGNATURE", "1") == "1":
        sig = request.headers.get("X-Twilio-Signature")
        full_url = str(request.url)
        # Quando atrás de proxy reverso (ngrok), a URL externa pode
        # diferir da interna. Permitir override via env.
        override = os.getenv("TWILIO_PUBLIC_URL")
        if override:
            from urllib.parse import urlparse, urlunparse
            internal = urlparse(full_url)
            ext = urlparse(override.rstrip("/"))
            full_url = urlunparse((
                ext.scheme, ext.netloc, internal.path,
                internal.params, internal.query, internal.fragment,
            ))
        if not TW.validate_signature(full_url,
                                     {k: str(v) for k, v in form_dict.items()},
                                     sig):
            logger.warning("Assinatura Twilio inválida para URL=%s", full_url)
            raise HTTPException(status_code=403, detail="Invalid signature")

    threading.Thread(
        target=_process_in_background,
        args=({k: str(v) for k, v in form_dict.items()},),
        daemon=True,
    ).start()

    return Response(status_code=200, content="")


@router.get("/twilio/health")
def twilio_health() -> Dict[str, Any]:
    """Health check + reporta se as envs de Twilio estão presentes."""
    have = {
        "TWILIO_ACCOUNT_SID": bool(os.getenv("TWILIO_ACCOUNT_SID")),
        "TWILIO_AUTH_TOKEN": bool(os.getenv("TWILIO_AUTH_TOKEN")),
        "TWILIO_WHATSAPP_NUMBER": bool(os.getenv("TWILIO_WHATSAPP_NUMBER")),
        "ANTHROPIC_API_KEY": bool(os.getenv("ANTHROPIC_API_KEY")),
    }
    return {
        "status": "ok" if all(have.values()) else "missing_env",
        "env": have,
        "validate_signature": os.getenv("TWILIO_VALIDATE_SIGNATURE", "1") == "1",
    }
