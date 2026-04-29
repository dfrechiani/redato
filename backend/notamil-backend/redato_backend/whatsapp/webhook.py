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
from typing import Any, Dict, Mapping
from urllib.parse import urlparse, urlunparse

from fastapi import APIRouter, Form, HTTPException, Request, Response

from redato_backend.whatsapp import twilio_provider as TW
from redato_backend.whatsapp.bot import handle_inbound


logger = logging.getLogger(__name__)
router = APIRouter()


# ──────────────────────────────────────────────────────────────────────
# URL pra validação de assinatura — atrás de proxy reverso
# ──────────────────────────────────────────────────────────────────────
# Twilio assina a URL pública (https://...). Quando o app está atrás de
# proxy (Railway, ngrok, fly.io), `request.url` chega como `http://`
# porque o TLS termina no proxy. HMAC compara strings literais →
# assinatura falha.
#
# Hierarquia de fontes (mais forte → mais fraca):
#   1. TWILIO_PUBLIC_URL env explícito (override total — recomendado em
#      produção pra blindar a configuração).
#   2. Headers X-Forwarded-Proto + X-Forwarded-Host (padrão em proxies).
#   3. Heurística: se host termina em `.railway.app`, força https.
#   4. Fallback: usa request.url como veio.

_RAILWAY_HOST_SUFFIXES = (".railway.app", ".up.railway.app")


def _force_https_for_known_proxies(url: str) -> str:
    """Se a URL aponta pra host conhecido que sempre termina TLS no proxy,
    força scheme https. Hoje cobre Railway. Adicionar fly.io etc. aqui se
    surgir o mesmo problema."""
    parsed = urlparse(url)
    host = (parsed.netloc or "").split(":")[0].lower()
    if not host.endswith(_RAILWAY_HOST_SUFFIXES):
        return url
    if parsed.scheme == "https":
        return url
    return urlunparse((
        "https", parsed.netloc, parsed.path, parsed.params,
        parsed.query, parsed.fragment,
    ))


def _build_validation_url(
    request_url: str,
    headers: Mapping[str, str],
    public_url_env: str = "",
) -> str:
    """Monta a URL exata que o Twilio assinou. Pure function — testável.

    Hierarquia (na ordem):
    1. `public_url_env` (TWILIO_PUBLIC_URL) → usa scheme+host dele,
       preserva path/query do request real (caso o webhook esteja em
       /twilio/webhook ou outro path).
    2. Headers `X-Forwarded-Proto` / `X-Forwarded-Host` (proxy) →
       reconstrói scheme/host a partir deles.
    3. Heurística: se request.url aponta pra Railway (qualquer
       *.railway.app), força https.
    4. Fallback: devolve request_url inalterado.
    """
    internal = urlparse(request_url)

    # (1) override total via env
    if public_url_env:
        ext = urlparse(public_url_env.rstrip("/"))
        if ext.scheme and ext.netloc:
            return urlunparse((
                ext.scheme, ext.netloc, internal.path,
                internal.params, internal.query, internal.fragment,
            ))

    # (2) headers de proxy reverso (case-insensitive)
    h = {k.lower(): v for k, v in headers.items()}
    fwd_proto = (h.get("x-forwarded-proto") or "").split(",")[0].strip().lower()
    fwd_host = (h.get("x-forwarded-host") or "").split(",")[0].strip()

    if fwd_proto and fwd_host:
        return urlunparse((
            fwd_proto, fwd_host, internal.path,
            internal.params, internal.query, internal.fragment,
        ))
    if fwd_proto and not fwd_host:
        # Só o proto vem (caso Railway atual): preserva host do request.
        return urlunparse((
            fwd_proto, internal.netloc, internal.path,
            internal.params, internal.query, internal.fragment,
        ))

    # (3) heurística defensiva pra Railway (sem header de proxy)
    return _force_https_for_known_proxies(request_url)


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
        full_url = _build_validation_url(
            request_url=str(request.url),
            headers=dict(request.headers),
            public_url_env=os.getenv("TWILIO_PUBLIC_URL", ""),
        )
        if not TW.validate_signature(full_url,
                                     {k: str(v) for k, v in form_dict.items()},
                                     sig):
            logger.warning(
                "Assinatura Twilio inválida. "
                "url_validacao=%s request_url=%s "
                "x-forwarded-proto=%r x-forwarded-host=%r "
                "twilio_public_url=%r",
                full_url, str(request.url),
                request.headers.get("x-forwarded-proto"),
                request.headers.get("x-forwarded-host"),
                os.getenv("TWILIO_PUBLIC_URL", ""),
            )
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
        "twilio_public_url_set": bool(os.getenv("TWILIO_PUBLIC_URL")),
    }
