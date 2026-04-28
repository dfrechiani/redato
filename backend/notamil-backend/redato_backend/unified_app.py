"""App unificado pra deploy single-service no Railway (M8+).

Junta os routers do portal (admin/auth/portal) com o webhook do bot
WhatsApp num único FastAPI app, exposto numa única porta. Em dev local
você pode preferir os dois separados (`make demo`), mas pra Railway é
1 serviço (mais simples, mais barato — não paga por 2 dynos).

**Não tem conflito de prefix** entre portal e bot:
- portal: `/admin/*`, `/auth/*`, `/portal/*`
- bot:    `/twilio/webhook`, `/twilio/health`

Bootstrap do bot (apply_patches, init SQLite) é executado uma vez na
import time — antes de carregar os routers.

Uso (Railway):
    uvicorn redato_backend.unified_app:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import FastAPI


def _bootstrap_env() -> None:
    """Carrega `.env` do backend se existir. Em Railway, vars vêm
    direto do environment — `.env` não existe, mas a função é
    inofensiva."""
    backend = Path(__file__).resolve().parents[1]
    env_path = backend / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip()
            if not os.environ.get(k):
                os.environ[k] = v


_bootstrap_env()

# Bot setup: stub se REDATO_DEV_OFFLINE=1, senão usa Anthropic real.
# Em Railway de produção, REDATO_DEV_OFFLINE=0 e o módulo `dev_offline`
# nem é importado — evita carregar 4k linhas de stub e qualquer
# top-level que dependa do layout do repo de dev.
if os.environ.get("REDATO_DEV_OFFLINE") == "1":
    from redato_backend.dev_offline import apply_patches  # noqa: E402
    apply_patches()

# Log level configurável via env. Default INFO.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

# Init SQLite legado do bot (FSM state). Em Railway, vai pra volume
# persistente em /app/data/whatsapp/redato.db (configurar
# REDATO_WHATSAPP_DB no env).
from redato_backend.whatsapp import persistence as _P  # noqa: E402
_P.init_db()

# ──────────────────────────────────────────────────────────────────────
# App
# ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Redato Portal — Unified (portal + bot)",
    description=(
        "Single-service deploy: portal API (/admin, /auth, /portal) + "
        "bot WhatsApp webhook (/twilio). Pra arquitetura, ver "
        "docs/redato/v3/DEPLOY_RAILWAY.md."
    ),
)

# Portal routers (admin, auth, portal)
from redato_backend.portal.admin_api import router as admin_router  # noqa: E402
from redato_backend.portal.auth.api import router as auth_router  # noqa: E402
from redato_backend.portal.portal_api import router as portal_router  # noqa: E402
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(portal_router)

# Bot router (webhook Twilio)
from redato_backend.whatsapp.webhook import router as twilio_router  # noqa: E402
app.include_router(twilio_router)


@app.get("/")
def root() -> dict:
    """Endpoint informativo. Probe-friendly."""
    return {
        "service": "redato-unified",
        "version": "M8",
        "endpoints": {
            "admin_health": "GET /admin/health",
            "admin_health_full": "GET /admin/health/full",
            "auth_login": "POST /auth/login",
            "auth_me": "GET /auth/me",
            "portal_turmas": "GET /portal/turmas",
            "portal_pdf_turma": "POST /portal/pdfs/dashboard-turma/{id}",
            "twilio_webhook": "POST /twilio/webhook",
            "twilio_health": "GET /twilio/health",
        },
    }
