"""JWT service — encode/decode com JTI, audience, issuer.

Algoritmo HS256 (suficiente pra Fase B+ single-tenant). Migrar pra
RS256 só se virar B2B com múltiplos consumidores.

JTI (JWT ID) é gerado em encode pra permitir blocklist em logout.
"""
from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt


JWT_AUDIENCE = "redato-portal"
JWT_ISSUER = "redato-backend"
JWT_ALGORITHM = "HS256"

# Durações
SESSAO_PADRAO = timedelta(hours=8)
SESSAO_LEMBRAR = timedelta(days=30)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _secret_key() -> str:
    """Lê JWT_SECRET_KEY do env. Fail loud se ausente ou < 32 chars."""
    key = os.getenv("JWT_SECRET_KEY")
    if not key:
        raise RuntimeError(
            "JWT_SECRET_KEY não configurada. Defina no .env "
            "(min 32 chars). Sugestão: `python -c "
            "'import secrets; print(secrets.token_hex(32))'`"
        )
    if len(key) < 32:
        raise RuntimeError(
            f"JWT_SECRET_KEY tem {len(key)} chars; mínimo 32. "
            "Gere uma nova: `python -c "
            "'import secrets; print(secrets.token_hex(32))'`"
        )
    return key


@dataclass
class TokenPayload:
    user_id: str        # uuid str
    papel: str          # "coordenador" | "professor"
    escola_id: str      # uuid str
    jti: str
    iat: datetime
    exp: datetime

    def to_dict(self) -> Dict[str, Any]:
        return {
            "sub": self.user_id,
            "papel": self.papel,
            "escola_id": self.escola_id,
            "jti": self.jti,
            "iat": int(self.iat.timestamp()),
            "exp": int(self.exp.timestamp()),
            "aud": JWT_AUDIENCE,
            "iss": JWT_ISSUER,
        }


def encode_token(
    user_id: str, papel: str, escola_id: str,
    *, lembrar_de_mim: bool = False,
) -> tuple[str, TokenPayload]:
    """Gera JWT assinado. Retorna (token_string, payload_obj)."""
    if papel not in ("coordenador", "professor"):
        raise ValueError(f"papel inválido: {papel}")
    iat = _utc_now()
    duration = SESSAO_LEMBRAR if lembrar_de_mim else SESSAO_PADRAO
    exp = iat + duration
    payload = TokenPayload(
        user_id=user_id, papel=papel, escola_id=escola_id,
        jti=str(uuid.uuid4()),
        iat=iat, exp=exp,
    )
    token = jwt.encode(
        payload.to_dict(), _secret_key(), algorithm=JWT_ALGORITHM,
    )
    return token, payload


def decode_token(token: str) -> Dict[str, Any]:
    """Decode + valida assinatura, exp, audience, issuer.

    Retorna dict com claims. Levanta:
    - jwt.ExpiredSignatureError se exp passou
    - jwt.InvalidAudienceError se aud errado
    - jwt.InvalidIssuerError se iss errado
    - jwt.InvalidTokenError em qualquer outro erro
    """
    return jwt.decode(
        token, _secret_key(),
        algorithms=[JWT_ALGORITHM],
        audience=JWT_AUDIENCE,
        issuer=JWT_ISSUER,
        options={"require": ["exp", "iat", "sub", "jti", "aud", "iss"]},
    )


def expira_em_segundos(payload: TokenPayload) -> int:
    return max(0, int((payload.exp - _utc_now()).total_seconds()))
