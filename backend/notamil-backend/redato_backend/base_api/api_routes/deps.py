from typing import Any, Dict, Iterable, Set

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

from redato_backend.base_api.functions.models import UserRole
from redato_backend.shared.firebase import FirebaseService
from redato_backend.shared.logger import logger


_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")
_firebase_service = FirebaseService()


def require_auth(token: str = Depends(_oauth2_scheme)) -> Dict[str, Any]:
    """Verify the Firebase ID token and return the decoded claims.

    Raises 401 if the token is missing or invalid.
    """
    decoded = _firebase_service.verify_token(token)
    if not decoded.get("uid"):
        raise HTTPException(
            status_code=401, detail="Token is missing a user identifier."
        )
    return decoded


def require_roles(*allowed_roles: str):
    """Dependency factory: only allow callers whose role claim is in `allowed_roles`.

    Usage:
        @router.post(..., dependencies=[Depends(require_roles("school_admin"))])
        # or, if you need the decoded token in the handler:
        def handler(user = Depends(require_roles("school_admin"))):
            ...
    """
    allowed: Set[str] = {r.lower() for r in allowed_roles}

    def _dep(user: Dict[str, Any] = Depends(require_auth)) -> Dict[str, Any]:
        role = (user.get("role") or "").lower()
        if role not in allowed:
            logger.warning(
                f"Forbidden: uid={user.get('uid')} role={role!r} tried to access endpoint requiring roles {sorted(allowed)}"  # noqa: E501
            )
            raise HTTPException(
                status_code=403,
                detail="Your account does not have permission to perform this action.",
            )
        return user

    return _dep


# Common role bundles for readability
def require_admin(user: Dict[str, Any] = Depends(
    require_roles(UserRole.SCHOOL_ADMIN.value, UserRole.SYSTEM_ADMIN.value)
)) -> Dict[str, Any]:
    return user


def require_professor_or_admin(user: Dict[str, Any] = Depends(
    require_roles(
        UserRole.PROFESSOR.value,
        UserRole.SCHOOL_ADMIN.value,
        UserRole.SYSTEM_ADMIN.value,
    )
)) -> Dict[str, Any]:
    return user


def assert_known_role(role: str) -> str:
    """Normalize and validate a role string against UserRole enum."""
    normalized = (role or "").lower()
    valid = {r.value.lower() for r in UserRole}
    if normalized not in valid:
        raise HTTPException(
            status_code=401, detail=f"Unknown role claim: {role!r}"
        )
    return normalized


def _roles(roles: Iterable[str]) -> Set[str]:
    return {r.lower() for r in roles}
