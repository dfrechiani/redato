"""Permissões — funções puras de autorização (M3).

Sem side-effects, sem queries de DB embutidas. Todas recebem
`AuthenticatedUser` e os IDs/objetos relevantes; retornam bool.

Quem precisa do estado do banco pra decidir (ex.: "este professor é
responsável por esta turma?") recebe o objeto Turma já carregado pelo
caller. Mantém testabilidade.
"""
from __future__ import annotations

import uuid
from typing import Optional

from redato_backend.portal.auth.middleware import AuthenticatedUser
from redato_backend.portal.models import Turma


def can_view_escola(auth: AuthenticatedUser, escola_id: uuid.UUID) -> bool:
    """Coordenador OU professor da própria escola."""
    return auth.escola_id == escola_id


def can_view_turma(auth: AuthenticatedUser, turma: Turma) -> bool:
    """Coordenador da escola da turma OU professor responsável pela turma."""
    if auth.papel == "coordenador":
        return turma.escola_id == auth.escola_id
    if auth.papel == "professor":
        return turma.professor_id == auth.user_id
    return False


def can_create_atividade(auth: AuthenticatedUser, turma: Turma) -> bool:
    """Só professor responsável pela turma cria atividade.
    Coordenador NÃO cria — ele só consulta dashboards."""
    return (
        auth.papel == "professor"
        and turma.professor_id == auth.user_id
    )


def can_view_dashboard_turma(auth: AuthenticatedUser, turma: Turma) -> bool:
    """Mesma regra de can_view_turma."""
    return can_view_turma(auth, turma)


def can_view_dashboard_escola(
    auth: AuthenticatedUser, escola_id: uuid.UUID,
) -> bool:
    """Só coordenador da própria escola vê dashboard agregado."""
    return auth.papel == "coordenador" and auth.escola_id == escola_id
