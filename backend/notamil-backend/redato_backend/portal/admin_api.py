"""Endpoints administrativos do portal (M2 + proteções de M3).

Endpoints, todos protegidos por header `X-Admin-Token`:

    POST /admin/import-planilha    — importa planilha (multipart)
    POST /admin/send-welcome-emails — dispara emails (max 100 + confirmar)
    GET  /admin/health              — health check (sem token)

Auth simples via token compartilhado em env `ADMIN_TOKEN`. JWT do
portal user-facing fica nos endpoints `/auth/*` (M3).
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, Header, HTTPException, Request,
    UploadFile,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from redato_backend.portal.db import get_engine
from redato_backend.portal.email_service import send_welcome_emails
from redato_backend.portal.importer import run_import
from redato_backend.portal.models import Coordenador, Professor


# Limite hardcoded de envio em massa por chamada (proteção contra
# acidente de mandar pra base inteira por engano).
MAX_EMAILS_POR_CHAMADA = 100

_AUDIT_LOG = (
    Path(__file__).resolve().parents[2] / "data" / "portal" / "audit_log.jsonl"
)


router = APIRouter(prefix="/admin", tags=["admin"])


# ──────────────────────────────────────────────────────────────────────
# Auth — X-Admin-Token (M3 troca por JWT)
# ──────────────────────────────────────────────────────────────────────

def require_admin_token(
    x_admin_token: Optional[str] = Header(None),
) -> None:
    """Valida header X-Admin-Token contra env ADMIN_TOKEN."""
    expected = os.getenv("ADMIN_TOKEN")
    if not expected:
        raise HTTPException(
            status_code=503,
            detail="ADMIN_TOKEN não configurado no servidor.",
        )
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="Invalid admin token")


def _get_session() -> Session:
    return Session(get_engine())


# ──────────────────────────────────────────────────────────────────────
# POST /admin/import-planilha
# ──────────────────────────────────────────────────────────────────────

@router.post("/import-planilha")
async def import_planilha(
    file: UploadFile = File(...),
    dry_run: bool = Form(True),
    ano_letivo: Optional[int] = Form(None),
    rollback_on_error: bool = Form(True),
    _: None = Depends(require_admin_token),
) -> dict:
    """Importa XLSX ou CSV. Retorna o relatório JSON do importador.

    Form fields:
    - `file`: arquivo .xlsx ou .csv
    - `dry_run`: bool (default True). False = commit.
    - `ano_letivo`: int opcional (default ano corrente UTC)
    - `rollback_on_error`: bool (default True)
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Arquivo sem nome")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in (".xlsx", ".xlsm", ".csv"):
        raise HTTPException(
            status_code=400,
            detail=f"Formato {suffix} não suportado. Use .xlsx ou .csv.",
        )

    # Salva temp pra parser
    content = await file.read()
    with tempfile.NamedTemporaryFile(
        suffix=suffix, delete=False
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        with _get_session() as session:
            modo = "dry-run" if dry_run else "commit"
            report = run_import(
                session, tmp_path, modo=modo,
                ano_letivo=ano_letivo,
                rollback_on_error=rollback_on_error,
            )
        return report.to_dict()
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


# ──────────────────────────────────────────────────────────────────────
# POST /admin/send-welcome-emails
# ──────────────────────────────────────────────────────────────────────

class SendWelcomeRequest(BaseModel):
    escola_id: Optional[str] = Field(
        None, description="UUID da escola. Se setado, restringe envio."
    )
    professor_emails: Optional[List[str]] = Field(
        None, description="Lista de emails. Se setada, restringe envio."
    )
    coordenador_emails: Optional[List[str]] = Field(
        None, description="Lista de emails. Se setada, restringe envio."
    )
    overwrite_existing_token: bool = Field(
        False,
        description=(
            "Se True, gera novo token mesmo pra users que já têm senha. "
            "Útil pra reset emergencial. Default False."
        ),
    )
    confirmar_envio: bool = Field(
        False,
        description=(
            "OBRIGATÓRIO True pra disparar de fato. Proteção contra envio "
            "acidental em massa. Sem isso, endpoint retorna 400 com "
            "preview do que seria enviado."
        ),
    )


def _audit_log(record: dict) -> None:
    """Append-only JSONL pra auditoria de operações sensíveis."""
    _AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    record_full = {
        "ts": datetime.now(timezone.utc).isoformat(),
        **record,
    }
    try:
        with _AUDIT_LOG.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record_full, ensure_ascii=False,
                                default=str) + "\n")
    except Exception:  # noqa: BLE001
        # Não falha a operação por bug de log.
        pass


def _count_pending_recipients(
    session: Session, body: "SendWelcomeRequest",
) -> int:
    """Conta quantos users seriam notificados (sem senha definida ou
    com overwrite=True). Usado pra preview e pra enforce do limite.

    M4 refactor: delega pra `email_service.filter_pending_users`. Sem
    duplicação de query/filtros entre count e send.
    """
    import uuid as _uuid
    from redato_backend.portal.email_service import filter_pending_users

    escola_uuid = None
    if body.escola_id:
        try:
            escola_uuid = _uuid.UUID(body.escola_id)
        except ValueError:
            return 0

    coords, profs = filter_pending_users(
        session,
        escola_id=escola_uuid,
        coordenador_emails=body.coordenador_emails,
        professor_emails=body.professor_emails,
        only_no_password=not body.overwrite_existing_token,
    )
    return len(coords) + len(profs)


@router.post("/send-welcome-emails")
def post_send_welcome_emails(
    body: SendWelcomeRequest,
    request: Request,
    _: None = Depends(require_admin_token),
) -> dict:
    """Dispara emails de primeiro acesso pros usuários selecionados.

    Proteções (M3):
    1. `confirmar_envio` deve ser True. Senão retorna 400 com preview
       de quantos seriam afetados.
    2. Limite hardcoded MAX_EMAILS_POR_CHAMADA. Acima disso 400.
    3. Cada chamada gera audit log em `data/portal/audit_log.jsonl`.

    Filtros (combinam com OR; se nenhum: TODOS sem senha):
    - `escola_id`: só dessa escola.
    - listas de emails: só esses.
    """
    import uuid as _uuid
    escola_uuid = None
    if body.escola_id:
        try:
            escola_uuid = _uuid.UUID(body.escola_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"escola_id inválido (não é UUID): {body.escola_id}",
            )

    client_ip = (
        request.client.host if request.client else "?"
    )

    with _get_session() as session:
        n_alvo = _count_pending_recipients(session, body)

        if not body.confirmar_envio:
            _audit_log({
                "op": "send-welcome-preview",
                "ip": client_ip,
                "escola_id": body.escola_id,
                "n_alvo": n_alvo,
            })
            raise HTTPException(
                status_code=400,
                detail={
                    "msg": ("confirmar_envio=true é obrigatório pra disparar. "
                            "Esta resposta é só preview."),
                    "n_alvo": n_alvo,
                    "max_permitido": MAX_EMAILS_POR_CHAMADA,
                },
            )

        if n_alvo > MAX_EMAILS_POR_CHAMADA:
            _audit_log({
                "op": "send-welcome-rejected-limite",
                "ip": client_ip,
                "escola_id": body.escola_id,
                "n_alvo": n_alvo, "limite": MAX_EMAILS_POR_CHAMADA,
            })
            raise HTTPException(
                status_code=400,
                detail={
                    "msg": (f"Tentativa de enviar {n_alvo} emails excede "
                            f"limite de {MAX_EMAILS_POR_CHAMADA} por chamada. "
                            f"Filtre por escola_id ou listas específicas."),
                    "n_alvo": n_alvo,
                    "max_permitido": MAX_EMAILS_POR_CHAMADA,
                },
            )

        result = send_welcome_emails(
            session,
            escola_id=escola_uuid,
            coordenador_emails=body.coordenador_emails,
            professor_emails=body.professor_emails,
            overwrite_existing_token=body.overwrite_existing_token,
        )

        _audit_log({
            "op": "send-welcome-executed",
            "ip": client_ip,
            "escola_id": body.escola_id,
            **result.to_dict(),
        })
    return result.to_dict()


# ──────────────────────────────────────────────────────────────────────
# Health do admin (não exige token)
# ──────────────────────────────────────────────────────────────────────

@router.get("/health")
def admin_health() -> dict:
    return {
        "status": "ok",
        "admin_token_set": bool(os.getenv("ADMIN_TOKEN")),
        "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY")),
        "database_url_set": bool(os.getenv("DATABASE_URL")),
    }


# ──────────────────────────────────────────────────────────────────────
# Health full (M8) — checagem profunda pra Railway / debugging
# ──────────────────────────────────────────────────────────────────────

@router.get("/health/full")
def admin_health_full() -> dict:
    """Health detalhado: db, sendgrid, twilio, storage de PDFs.

    Não requer admin token — feito pra ser pollado por healthchecks
    do Railway. Não vaza segredos; só reporta presença de configs.
    """
    from sqlalchemy import text
    from redato_backend.portal import pdf_generator as PDF

    out = {
        "status": "ok",
        "checks": {
            "admin_token": bool(os.getenv("ADMIN_TOKEN")),
            "sendgrid_configured": bool(os.getenv("SENDGRID_API_KEY")),
            "twilio_configured": bool(os.getenv("TWILIO_ACCOUNT_SID")),
            "database_url_set": bool(os.getenv("DATABASE_URL")),
            "jwt_secret_set": bool(os.getenv("JWT_SECRET_KEY")),
        },
    }

    # DB ping
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        out["checks"]["db_ping"] = True
    except Exception as exc:  # noqa: BLE001
        out["checks"]["db_ping"] = False
        out["checks"]["db_error"] = f"{type(exc).__name__}: {exc}"
        out["status"] = "degraded"

    # Storage de PDFs
    try:
        root = PDF.storage_root()
        root.mkdir(parents=True, exist_ok=True)
        # Tenta criar+remover um arquivo temp pra validar permissão write
        probe = root / ".healthprobe"
        probe.write_bytes(b"x")
        probe.unlink(missing_ok=True)
        out["checks"]["storage_pdfs_writable"] = True
        out["checks"]["storage_pdfs_path"] = str(root)
    except Exception as exc:  # noqa: BLE001
        out["checks"]["storage_pdfs_writable"] = False
        out["checks"]["storage_error"] = f"{type(exc).__name__}: {exc}"
        out["status"] = "degraded"

    return out


# ──────────────────────────────────────────────────────────────────────
# /admin/triggers/run — varre triggers automáticos (M8)
# ──────────────────────────────────────────────────────────────────────

@router.post("/triggers/run", dependencies=[Depends(require_admin_token)])
def admin_triggers_run() -> dict:
    """Dispara todos os triggers oportunistas. Idempotente via dedup
    no `triggers_log.jsonl`. Configurar cron externo (Railway/GitHub
    Actions) chamando isso 1× por dia.
    """
    from redato_backend.portal import triggers as TR
    res = TR.check_e_disparar_triggers()
    return {
        "encerradas_avisadas": res.encerradas_avisadas,
        "risco_avisados": res.risco_avisados,
        "skipped": res.skipped,
    }
