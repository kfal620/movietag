from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status

from app.core.settings import get_settings


@dataclass
class AuthenticatedUser:
    role: str


def _token_to_role(token: str) -> str | None:
    settings = get_settings()
    if settings.admin_token and token == settings.admin_token:
        return "admin"
    if settings.moderator_token and token == settings.moderator_token:
        return "moderator"
    return None


def get_current_user(authorization: str | None = Header(default=None)) -> AuthenticatedUser:
    """Validate the bearer token and map it to a role."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing authorization token",
        )

    token = authorization.split(" ", 1)[1]
    role = _token_to_role(token)
    if role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not grant access to this resource",
        )
    return AuthenticatedUser(role=role)


def require_role(*allowed_roles: str):
    def dependency(user: AuthenticatedUser = Depends(get_current_user)) -> AuthenticatedUser:
        if user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action",
            )
        return user

    return dependency
