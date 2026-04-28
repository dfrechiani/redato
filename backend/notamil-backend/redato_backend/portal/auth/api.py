"""Endpoints HTTP /auth/* — M3.

7 endpoints:
- POST /auth/login
- POST /auth/primeiro-acesso/validar
- POST /auth/primeiro-acesso/definir-senha
- POST /auth/reset-password/solicitar
- POST /auth/reset-password/confirmar
- POST /auth/logout
- GET  /auth/me
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from redato_backend.portal.auth.jwt_service import (
    encode_token, expira_em_segundos,
)
from redato_backend.portal.auth.middleware import (
    AuthenticatedUser, get_current_user,
)
from redato_backend.portal.auth.password import (
    hash_senha, validate_senha, verify_senha,
)
from redato_backend.portal.db import get_engine
from redato_backend.portal.email_service import (
    PRIMEIRO_ACESSO_VALID_DAYS, _gerar_token, _portal_url, _render,
    _load_template, _send,
    EmailEnvelope,
)
from redato_backend.portal.models import (
    Coordenador, Escola, Professor, TokenBlocklist,
)


router = APIRouter(prefix="/auth", tags=["auth"])


def _get_session() -> Session:
    return Session(get_engine())


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


# ──────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str
    lembrar_de_mim: bool = False


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    papel: str
    nome: str
    escola_id: str


class PrimeiroAcessoValidarRequest(BaseModel):
    token: str = Field(min_length=8)


class PrimeiroAcessoValidarResponse(BaseModel):
    valido: bool
    email: Optional[str] = None
    nome: Optional[str] = None
    papel: Optional[str] = None
    escola_nome: Optional[str] = None


class DefinirSenhaRequest(BaseModel):
    token: str = Field(min_length=8)
    senha: str


class DefinirSenhaResponse(BaseModel):
    sucesso: bool = True
    redirect_to: str = "/auth/login"


class SolicitarResetRequest(BaseModel):
    email: EmailStr


class ConfirmarResetRequest(BaseModel):
    token: str = Field(min_length=8)
    senha_nova: str


class MeResponse(BaseModel):
    id: str
    nome: str
    email: str
    papel: str
    escola_id: str
    escola_nome: str


# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────

def _find_user_by_token(
    session: Session, *, token: str, field: str,
) -> tuple[Optional[object], Optional[str]]:
    """Busca em coordenadores e professores. Retorna (user, papel) ou
    (None, None)."""
    # Coordenador
    col = getattr(Coordenador, field)
    coord = session.execute(
        select(Coordenador).where(col == token)
    ).scalar_one_or_none()
    if coord is not None:
        return coord, "coordenador"
    col = getattr(Professor, field)
    prof = session.execute(
        select(Professor).where(col == token)
    ).scalar_one_or_none()
    if prof is not None:
        return prof, "professor"
    return None, None


def _find_user_by_email(
    session: Session, email: str,
) -> tuple[Optional[object], Optional[str]]:
    email_l = email.lower()
    coord = session.execute(
        select(Coordenador).where(Coordenador.email == email_l)
    ).scalar_one_or_none()
    if coord is not None:
        return coord, "coordenador"
    prof = session.execute(
        select(Professor).where(Professor.email == email_l)
    ).scalar_one_or_none()
    if prof is not None:
        return prof, "professor"
    return None, None


# ──────────────────────────────────────────────────────────────────────
# POST /auth/login
# ──────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    with _get_session() as session:
        user, papel = _find_user_by_email(session, body.email)
        if user is None or not user.senha_hash:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha inválidos",
            )
        if not verify_senha(body.senha, user.senha_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou senha inválidos",
            )
        if not user.ativo:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Usuário inativo",
            )

        token, payload = encode_token(
            user_id=str(user.id),
            papel=papel,
            escola_id=str(user.escola_id),
            lembrar_de_mim=body.lembrar_de_mim,
        )
        user.ultimo_login_em = _utc_now()
        session.commit()

        return LoginResponse(
            access_token=token,
            expires_in=expira_em_segundos(payload),
            papel=papel,
            nome=user.nome,
            escola_id=str(user.escola_id),
        )


# ──────────────────────────────────────────────────────────────────────
# POST /auth/primeiro-acesso/validar
# ──────────────────────────────────────────────────────────────────────

@router.post("/primeiro-acesso/validar",
             response_model=PrimeiroAcessoValidarResponse)
def primeiro_acesso_validar(
    body: PrimeiroAcessoValidarRequest,
) -> PrimeiroAcessoValidarResponse:
    with _get_session() as session:
        user, papel = _find_user_by_token(
            session, token=body.token, field="primeiro_acesso_token",
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token de primeiro acesso não encontrado",
            )
        if (user.primeiro_acesso_expira_em is None
                or user.primeiro_acesso_expira_em < _utc_now()):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Token expirado",
            )
        escola = session.get(Escola, user.escola_id)
        return PrimeiroAcessoValidarResponse(
            valido=True,
            email=user.email,
            nome=user.nome,
            papel=papel,
            escola_nome=escola.nome if escola else None,
        )


# ──────────────────────────────────────────────────────────────────────
# POST /auth/primeiro-acesso/definir-senha
# ──────────────────────────────────────────────────────────────────────

@router.post("/primeiro-acesso/definir-senha",
             response_model=DefinirSenhaResponse)
def primeiro_acesso_definir_senha(
    body: DefinirSenhaRequest,
) -> DefinirSenhaResponse:
    err = validate_senha(body.senha)
    if err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Senha fraca: {err}",
        )
    with _get_session() as session:
        user, _papel = _find_user_by_token(
            session, token=body.token, field="primeiro_acesso_token",
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token não encontrado",
            )
        if (user.primeiro_acesso_expira_em is None
                or user.primeiro_acesso_expira_em < _utc_now()):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Token expirado",
            )
        user.senha_hash = hash_senha(body.senha)
        user.primeiro_acesso_token = None
        user.primeiro_acesso_expira_em = None
        session.commit()
    return DefinirSenhaResponse()


# ──────────────────────────────────────────────────────────────────────
# POST /auth/reset-password/solicitar
# ──────────────────────────────────────────────────────────────────────

@router.post("/reset-password/solicitar")
def reset_password_solicitar(body: SolicitarResetRequest) -> dict:
    """Sempre 200 — anti-enumeração de emails."""
    with _get_session() as session:
        user, papel = _find_user_by_email(session, body.email)
        if user is None or not user.ativo:
            return {"sucesso": True}

        # Gera reset token (uuid hex de 64 chars), valida 2h
        user.reset_password_token = secrets.token_hex(32)
        user.reset_password_expira_em = _utc_now() + timedelta(hours=2)
        session.commit()

        # Dispara email (SendGrid ou dry-run)
        portal = _portal_url()
        link = f"{portal}/reset-password?token={user.reset_password_token}"
        primeiro_nome = (user.nome or "").split()[0] or user.nome or papel
        try:
            tpl = _load_template("reset_password.html")
            html = _render(
                tpl, nome=user.nome or "", primeiro_nome=primeiro_nome,
                link=link, validade_horas="2",
            )
        except FileNotFoundError:
            html = (
                f"<p>Link de reset (válido 2h):</p>"
                f"<p><a href='{link}'>{link}</a></p>"
            )
        text = (
            f"Olá, {primeiro_nome}.\n\n"
            f"Pra redefinir sua senha, acesse:\n{link}\n\n"
            f"Link válido por 2 horas. Se você não pediu este reset, "
            f"ignore este email.\n\nEquipe Redato"
        )
        envelope = EmailEnvelope(
            to_email=user.email, to_name=user.nome or "",
            subject="Redato — redefinir senha",
            html=html, text_fallback=text,
        )
        _send(envelope)
    return {"sucesso": True}


# ──────────────────────────────────────────────────────────────────────
# POST /auth/reset-password/confirmar
# ──────────────────────────────────────────────────────────────────────

@router.post("/reset-password/confirmar")
def reset_password_confirmar(body: ConfirmarResetRequest) -> dict:
    err = validate_senha(body.senha_nova)
    if err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Senha fraca: {err}",
        )
    with _get_session() as session:
        user, _papel = _find_user_by_token(
            session, token=body.token, field="reset_password_token",
        )
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Token de reset não encontrado",
            )
        if (user.reset_password_expira_em is None
                or user.reset_password_expira_em < _utc_now()):
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="Token expirado",
            )
        user.senha_hash = hash_senha(body.senha_nova)
        user.reset_password_token = None
        user.reset_password_expira_em = None
        session.commit()
    return {"sucesso": True}


# ──────────────────────────────────────────────────────────────────────
# POST /auth/logout
# ──────────────────────────────────────────────────────────────────────

@router.post("/logout")
def logout(auth: AuthenticatedUser = Depends(get_current_user)) -> dict:
    """Adiciona JTI à blocklist até exp natural."""
    with _get_session() as session:
        existing = session.execute(
            select(TokenBlocklist).where(TokenBlocklist.token_jti == auth.jti)
        ).scalar_one_or_none()
        if existing is None:
            session.add(TokenBlocklist(
                token_jti=auth.jti, exp_original=auth.exp,
            ))
            session.commit()
    return {"sucesso": True}


# ──────────────────────────────────────────────────────────────────────
# GET /auth/me
# ──────────────────────────────────────────────────────────────────────

@router.get("/me", response_model=MeResponse)
def me(auth: AuthenticatedUser = Depends(get_current_user)) -> MeResponse:
    with _get_session() as session:
        escola = session.get(Escola, auth.escola_id)
        escola_nome = escola.nome if escola else ""
    return MeResponse(
        id=str(auth.user_id), nome=auth.nome, email=auth.email,
        papel=auth.papel, escola_id=str(auth.escola_id),
        escola_nome=escola_nome,
    )


# ──────────────────────────────────────────────────────────────────────
# POST /auth/perfil/mudar-senha (M6)
# ──────────────────────────────────────────────────────────────────────

class MudarSenhaRequest(BaseModel):
    senha_atual: str
    senha_nova: str


@router.post("/perfil/mudar-senha")
def mudar_senha(
    body: MudarSenhaRequest,
    auth: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Verifica senha_atual + atualiza pra senha_nova. Mantém sessão atual.

    Outras sessões do mesmo user continuam válidas — pra invalidar todas
    use /auth/perfil/sair-todas-sessoes.
    """
    err = validate_senha(body.senha_nova)
    if err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Senha fraca: {err}",
        )
    with _get_session() as session:
        if auth.papel == "coordenador":
            user = session.get(Coordenador, auth.user_id)
        else:
            user = session.get(Professor, auth.user_id)
        if user is None or not user.senha_hash:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )
        if not verify_senha(body.senha_atual, user.senha_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Senha atual incorreta",
            )
        user.senha_hash = hash_senha(body.senha_nova)
        session.commit()
    return {"sucesso": True}


# ──────────────────────────────────────────────────────────────────────
# POST /auth/perfil/sair-todas-sessoes (M6)
# ──────────────────────────────────────────────────────────────────────

@router.post("/perfil/sair-todas-sessoes")
def sair_todas_sessoes(
    auth: AuthenticatedUser = Depends(get_current_user),
) -> dict:
    """Invalida todos os JWTs ativos do user (incluindo o atual).

    Implementação: seta `sessoes_invalidadas_em = now()`. Middleware
    rejeita tokens com `iat < sessoes_invalidadas_em`.
    """
    with _get_session() as session:
        if auth.papel == "coordenador":
            user = session.get(Coordenador, auth.user_id)
        else:
            user = session.get(Professor, auth.user_id)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Usuário não encontrado",
            )
        user.sessoes_invalidadas_em = _utc_now()
        session.commit()
    return {"sucesso": True}
