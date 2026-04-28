"""Auth middleware (FastAPI dependencies) — M3.

`AuthenticatedUser` envelopa Coordenador ou Professor + papel inferido.
Endpoints protegidos declaram dependência via `Depends(...)`.

Convenção:
- `get_current_user` retorna `AuthenticatedUser` (qualquer papel autenticado).
- `require_coordenador` retorna o user só se papel == "coordenador".
- `require_professor` retorna o user só se papel == "professor".
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Union

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from redato_backend.portal.auth.jwt_service import decode_token
from redato_backend.portal.db import get_engine
from redato_backend.portal.models import (
    Coordenador, Professor, TokenBlocklist,
)


bearer_scheme = HTTPBearer(auto_error=True)


@dataclass
class AuthenticatedUser:
    """Envelope com user (Coordenador ou Professor), papel e claims do JWT."""
    user: Union[Coordenador, Professor]
    papel: str   # "coordenador" | "professor"
    user_id: uuid.UUID
    escola_id: uuid.UUID
    jti: str
    exp: datetime

    @property
    def email(self) -> str:
        return self.user.email

    @property
    def nome(self) -> str:
        return self.user.nome


def _get_session() -> Session:
    return Session(get_engine())


def _is_blocklisted(session: Session, jti: str) -> bool:
    return session.execute(
        select(TokenBlocklist.id).where(TokenBlocklist.token_jti == jti)
    ).first() is not None


def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthenticatedUser:
    """Extrai e valida JWT. Levanta 401 em qualquer erro."""
    token = creds.credentials
    try:
        claims = decode_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token inválido: {type(exc).__name__}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    papel = claims.get("papel")
    sub = claims.get("sub")
    escola_id = claims.get("escola_id")
    jti = claims.get("jti")
    exp_ts = claims.get("exp")

    if papel not in ("coordenador", "professor") or not sub or not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Claims do token incompletos",
        )

    try:
        user_uuid = uuid.UUID(sub)
        escola_uuid = uuid.UUID(escola_id) if escola_id else None
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token com IDs malformados",
        )

    with _get_session() as session:
        if _is_blocklisted(session, jti):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token revogado (logout)",
            )
        if papel == "coordenador":
            user = session.get(Coordenador, user_uuid)
        else:
            user = session.get(Professor, user_uuid)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Usuário não existe",
            )
        if not user.ativo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo",
            )
        # M6 — "sair de todas as sessões": tokens emitidos antes desse
        # corte são rejeitados em massa.
        cut = getattr(user, "sessoes_invalidadas_em", None)
        if cut is not None:
            iat_ts = claims.get("iat")
            if iat_ts is None or int(iat_ts) < int(cut.timestamp()):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Sessão invalidada",
                )
        # Detach pra ser usado fora do session scope
        session.expunge(user)

    return AuthenticatedUser(
        user=user, papel=papel,
        user_id=user_uuid,
        escola_id=escola_uuid or user.escola_id,
        jti=jti,
        exp=datetime.fromtimestamp(int(exp_ts), tz=timezone.utc),
    )


def require_coordenador(
    auth: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if auth.papel != "coordenador":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint requer papel coordenador",
        )
    return auth


def require_professor(
    auth: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    if auth.papel != "professor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Endpoint requer papel professor",
        )
    return auth


def require_authenticated(
    auth: AuthenticatedUser = Depends(get_current_user),
) -> AuthenticatedUser:
    """Alias semântico — qualquer papel autenticado."""
    return auth
