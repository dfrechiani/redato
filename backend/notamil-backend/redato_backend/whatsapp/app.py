"""App FastAPI standalone pro bot WhatsApp em sandbox.

Uso (dev local):
    cd backend/notamil-backend
    REDATO_DEV_OFFLINE=1 \\
        uvicorn redato_backend.whatsapp.app:app --reload --port 8090

Em outro terminal:
    ngrok http 8090

Configurar URL ngrok (https) no console Twilio:
    twilio.com/console/sms/whatsapp/sandbox
    "WHEN A MESSAGE COMES IN" → POST → https://<ngrok>.ngrok.io/twilio/webhook
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI


# Setup mínimo: applies dev_offline patches (Firebase/BQ stub) e carrega
# .env do backend.
def _bootstrap() -> None:
    backend = Path(__file__).resolve().parents[2]
    env_path = backend / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip()
                if not os.environ.get(k):
                    os.environ[k] = v

    os.environ.setdefault("REDATO_DEV_OFFLINE", "1")
    os.environ.setdefault("REDATO_DEV_PERSIST", "0")
    os.environ.setdefault("REDATO_CLAUDE_MODEL", "claude-opus-4-7")
    os.environ.setdefault("REDATO_SCHEMA_FLAT", "1")
    os.environ.setdefault("REDATO_ENSEMBLE", "1")

    from redato_backend.dev_offline import apply_patches
    apply_patches()


_bootstrap()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)


app = FastAPI(title="Redato WhatsApp Bot (Sandbox)")

from redato_backend.whatsapp import persistence as _P  # noqa: E402
_P.init_db()

from redato_backend.whatsapp.webhook import router as webhook_router  # noqa: E402
app.include_router(webhook_router)


@app.get("/")
def root() -> dict:
    return {
        "service": "redato-whatsapp-sandbox",
        "endpoints": {
            "webhook": "POST /twilio/webhook",
            "health": "GET /twilio/health",
        },
        "next_steps": "Veja docs/redato/v3/caminho2_setup_passo_a_passo.md",
    }
