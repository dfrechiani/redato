"""Adaptador Twilio WhatsApp — Caminho 2 (Sandbox real).

Implementa o contrato de provedor:
- `parse_inbound(form_data)` — converte payload do webhook Twilio em
  `InboundMessage` (mesmo shape usado pelo simulator).
- `download_media(media_url)` — baixa a foto pra disco local.
- `send_text(phone, text)` — envia resposta via Twilio REST API.
- `validate_signature(...)` — verifica assinatura HMAC do webhook.

Variáveis de ambiente exigidas:
    TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER

`TWILIO_WHATSAPP_NUMBER` é o número Sandbox no formato `whatsapp:+14155238886`.
"""
from __future__ import annotations

import io
import logging
import mimetypes
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
from PIL import Image
from twilio.request_validator import RequestValidator
from twilio.rest import Client

from redato_backend.whatsapp.bot import InboundMessage


logger = logging.getLogger(__name__)


BACKEND = Path(__file__).resolve().parents[2]
PHOTOS_DIR = BACKEND / "data" / "whatsapp" / "photos"


def _require_env(name: str) -> str:
    val = os.environ.get(name)
    if not val:
        raise RuntimeError(
            f"Env var obrigatória ausente: {name}. Veja "
            f"docs/redato/v3/caminho2_setup_passo_a_passo.md."
        )
    return val


# ──────────────────────────────────────────────────────────────────────
# Cliente Twilio (lazy)
# ──────────────────────────────────────────────────────────────────────

_client: Optional[Client] = None


def _twilio_client() -> Client:
    global _client
    if _client is None:
        _client = Client(
            _require_env("TWILIO_ACCOUNT_SID"),
            _require_env("TWILIO_AUTH_TOKEN"),
        )
    return _client


# ──────────────────────────────────────────────────────────────────────
# Webhook signature validation
# ──────────────────────────────────────────────────────────────────────

def validate_signature(
    full_url: str,
    form_params: Dict[str, str],
    signature_header: Optional[str],
) -> bool:
    """Verifica X-Twilio-Signature contra o auth token.

    `full_url` deve ser a URL pública completa (https://...) que o
    Twilio chamou — incluindo path e query string. Importante quando
    rodar atrás de ngrok: usar a URL ngrok exata que está cadastrada
    no console Twilio.
    """
    if not signature_header:
        return False
    try:
        validator = RequestValidator(_require_env("TWILIO_AUTH_TOKEN"))
    except RuntimeError:
        return False
    return validator.validate(full_url, form_params, signature_header)


# ──────────────────────────────────────────────────────────────────────
# Inbound: webhook payload → InboundMessage
# ──────────────────────────────────────────────────────────────────────

def parse_inbound(form: Dict[str, Any]) -> InboundMessage:
    """Converte form-encoded body do webhook Twilio em InboundMessage.

    Twilio envia mídia como `MediaUrl0`, `MediaUrl1`, etc. Pegamos só a
    primeira. Caption (texto + foto) chega em `Body`.

    Para o Sandbox: o phone vem prefixado com `whatsapp:`, removemos.
    """
    raw_phone = (form.get("From") or "").strip()
    phone = raw_phone.replace("whatsapp:", "")

    text = (form.get("Body") or "").strip() or None

    image_path: Optional[str] = None
    num_media = int(form.get("NumMedia") or "0")
    if num_media > 0:
        media_url = form.get("MediaUrl0")
        media_type = form.get("MediaContentType0") or "image/jpeg"
        if media_url:
            image_path = str(download_media(media_url, media_type, phone))

    return InboundMessage(phone=phone, text=text, image_path=image_path)


def download_media(media_url: str, media_type: str,
                   phone_for_filename: str) -> Path:
    """Baixa mídia do Twilio (autenticado com SID + token), salva no
    disco local. Retorna path absoluto.

    Nota: URLs Twilio são públicas via redirect, mas o conteúdo final
    em S3/CDN é privado — precisa basic auth com SID + token.
    """
    PHOTOS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_phone = phone_for_filename.replace("+", "").replace(":", "")
    ext = mimetypes.guess_extension(media_type) or ".jpg"
    out_path = PHOTOS_DIR / f"{ts}_{safe_phone}{ext}"

    sid = _require_env("TWILIO_ACCOUNT_SID")
    token = _require_env("TWILIO_AUTH_TOKEN")
    resp = requests.get(media_url, auth=(sid, token), timeout=20,
                        allow_redirects=True)
    resp.raise_for_status()
    out_path.write_bytes(resp.content)

    # Sanity: tenta abrir como imagem. Se falhar, log mas mantém arquivo.
    try:
        Image.open(io.BytesIO(resp.content)).verify()
    except Exception as exc:
        logger.warning("Mídia baixada não é imagem válida: %r", exc)

    return out_path


# ──────────────────────────────────────────────────────────────────────
# Outbound: enviar resposta
# ──────────────────────────────────────────────────────────────────────

def send_text(phone: str, text: str) -> str:
    """Envia mensagem WhatsApp via Twilio REST API. Retorna SID da msg.

    `phone` no formato E.164 sem prefixo (`+5511999999999`). O número
    Sandbox vem de `TWILIO_WHATSAPP_NUMBER` (já com prefixo whatsapp:).
    """
    client = _twilio_client()
    from_ = _require_env("TWILIO_WHATSAPP_NUMBER")
    to = phone if phone.startswith("whatsapp:") else f"whatsapp:{phone}"
    if not from_.startswith("whatsapp:"):
        from_ = f"whatsapp:{from_}"

    msg = client.messages.create(from_=from_, to=to, body=text)
    return msg.sid


def send_replies(phone: str, replies: List[str]) -> List[str]:
    """Envia múltiplas respostas em ordem. Pequeno delay entre cada uma
    pra preservar ordem percebida no app do destinatário."""
    sids: List[str] = []
    for i, t in enumerate(replies):
        if i > 0:
            time.sleep(0.3)
        sids.append(send_text(phone, t))
    return sids
