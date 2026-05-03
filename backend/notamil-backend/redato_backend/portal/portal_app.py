"""FastAPI app standalone do portal — admin + auth endpoints.

Executar local:
    cd backend/notamil-backend
    uvicorn redato_backend.portal.portal_app:app --port 8091 --reload

Pré-requisitos:
- DATABASE_URL setada no .env
- alembic upgrade head já rodado
- ADMIN_TOKEN setado no .env (qualquer string secreta)
- JWT_SECRET_KEY setado no .env (≥32 chars)

Em M5+, este app pode ser mountado num app maior do portal web.
"""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI


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


_bootstrap()

from redato_backend.portal.admin_api import router as admin_router  # noqa: E402
from redato_backend.portal.auth.api import router as auth_router  # noqa: E402
from redato_backend.portal.portal_api import router as portal_router  # noqa: E402
from redato_backend.portal.jogo_api import router as jogo_router  # noqa: E402

app = FastAPI(title="Redato Portal — Admin + Auth + Portal API (M8)")
app.include_router(admin_router)
app.include_router(auth_router)
app.include_router(portal_router)
app.include_router(jogo_router)


@app.get("/")
def root() -> dict:
    return {
        "service": "redato-portal",
        "endpoints": {
            # Admin
            "admin_health": "GET /admin/health",
            "admin_import": "POST /admin/import-planilha",
            "admin_welcome": "POST /admin/send-welcome-emails",
            # Auth
            "auth_login": "POST /auth/login",
            "auth_primeiro_acesso_validar": "POST /auth/primeiro-acesso/validar",
            "auth_primeiro_acesso_definir": "POST /auth/primeiro-acesso/definir-senha",
            "auth_reset_solicitar": "POST /auth/reset-password/solicitar",
            "auth_reset_confirmar": "POST /auth/reset-password/confirmar",
            "auth_logout": "POST /auth/logout",
            "auth_me": "GET /auth/me",
            "auth_perfil_mudar_senha": "POST /auth/perfil/mudar-senha",
            "auth_perfil_sair_todas": "POST /auth/perfil/sair-todas-sessoes",
            # Portal — gestão M6
            "portal_missoes": "GET /portal/missoes",
            "portal_turmas_list": "GET /portal/turmas",
            "portal_turmas_detail": "GET /portal/turmas/{turma_id}",
            "portal_atividades_create": "POST /portal/atividades",
            "portal_atividade_detail": "GET /portal/atividades/{atividade_id}",
            "portal_atividade_patch": "PATCH /portal/atividades/{atividade_id}",
            "portal_atividade_encerrar": "POST /portal/atividades/{atividade_id}/encerrar",
            "portal_envio_feedback": "GET /portal/atividades/{atividade_id}/envios/{aluno_turma_id}",
            "portal_aluno_patch": "PATCH /portal/turmas/{turma_id}/alunos/{aluno_turma_id}",
            "portal_atividade_texto_notif": "GET /portal/atividades/{atividade_id}/texto-notificacao",
            "portal_atividade_notificar": "POST /portal/atividades/{atividade_id}/notificar",
            # M7 dashboards
            "portal_dashboard_turma": "GET /portal/turmas/{turma_id}/dashboard",
            "portal_dashboard_escola": "GET /portal/escolas/{escola_id}/dashboard",
            "portal_evolucao_aluno": "GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/evolucao",
            "portal_perfil_aluno": "GET /portal/turmas/{turma_id}/alunos/{aluno_turma_id}/perfil",
            "portal_envio_diagnosticar": "POST /portal/envios/{envio_id}/diagnosticar",
            # M8 PDF + admin triggers + health full
            "portal_pdf_turma": "POST /portal/pdfs/dashboard-turma/{turma_id}",
            "portal_pdf_escola": "POST /portal/pdfs/dashboard-escola/{escola_id}",
            "portal_pdf_aluno": "POST /portal/pdfs/evolucao-aluno/{turma_id}/{aluno_turma_id}",
            "portal_pdf_download": "GET /portal/pdfs/{pdf_id}/download",
            "portal_pdf_historico": "GET /portal/pdfs/historico",
            "admin_health_full": "GET /admin/health/full",
            "admin_triggers_run": "POST /admin/triggers/run",
        },
        "auth": "/admin: X-Admin-Token header. /auth + /portal: bearer JWT.",
    }
