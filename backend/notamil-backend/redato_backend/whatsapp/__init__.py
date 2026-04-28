"""Bot WhatsApp da Redato — Fase A (sandbox/dev).

Pipeline:
    [foto + missao_id] → OCR (Sonnet 4.6) → grade_mission (Sonnet/Opus
    por modo) → render_aluno_whatsapp → mensagem WhatsApp

Não inclui (Fase B/C):
- Geração de PDF agregado pro professor
- Onboarding pleno (matrícula em massa, convites)
- Dashboard web

Spec: docs/redato/v3/whatsapp_setup.md.
"""
from redato_backend.whatsapp.bot import handle_message, handle_inbound
from redato_backend.whatsapp.persistence import (
    init_db,
    get_aluno,
    save_interaction,
    list_interactions_by_turma,
)

__all__ = [
    "handle_message",
    "handle_inbound",
    "init_db",
    "get_aluno",
    "save_interaction",
    "list_interactions_by_turma",
]
