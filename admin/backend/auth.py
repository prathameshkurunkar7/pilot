from __future__ import annotations

from enum import StrEnum

from flask import g, request


_SITE_SCOPE_RESOLVER = "_site_scope_resolver"
_AUTH_POLICY = "_auth_policy"


class AuthPolicy(StrEnum):
    AUTHENTICATED = "authenticated"
    OPEN = "open"
    SETUP_CONDITIONAL = "setup-conditional"


def allow_unauthenticated(view):
    setattr(view, _AUTH_POLICY, AuthPolicy.OPEN)
    return view


def allow_during_setup(view):
    setattr(view, _AUTH_POLICY, AuthPolicy.SETUP_CONDITIONAL)
    return view


def endpoint_auth_policy(view) -> AuthPolicy:
    return getattr(view, _AUTH_POLICY, AuthPolicy.AUTHENTICATED)


def authenticate_request(config) -> bool:
    authorization = request.headers.get("Authorization", "")
    token = authorization[7:] if authorization.startswith("Bearer ") else None
    token = token or request.cookies.get("sid")
    if not token:
        return False
    claims = decode_session_token(token, config)
    if claims is None:
        return False
    g.jwt_claims = claims
    return True


def set_session_cookie(response, token: str, secure: bool) -> None:
    response.set_cookie(
        "sid",
        token,
        max_age=24 * 3600,
        httponly=True,
        secure=secure,
        samesite="Lax",
    )


def decode_session_token(token: str, config) -> dict | None:
    """Validate a session token against the local HS256 secret and, failing
    that, the trusted remote JWKS keys. Returns the token's claims or None."""
    from pilot.commands.generate_session import decode_token

    claims = decode_token(token, config.admin.jwt_secret)
    if claims is not None:
        return claims
    if config.admin.jwks_url:
        from .jwks import verify_jwks_token

        return verify_jwks_token(token, config.admin.jwks_url, config.admin.jwks_audience)
    return None


def require_scope(site):
    if callable(site):
        resolve = site
    else:

        def resolve(kwargs):
            return site

    def decorator(view):
        setattr(view, _SITE_SCOPE_RESOLVER, resolve)
        return view

    return decorator


def authorization_error(claims: dict | None, view, view_args: dict) -> str | None:
    from pilot.commands.generate_session import has_scope

    resolve_site = getattr(view, _SITE_SCOPE_RESOLVER, None)
    if resolve_site is not None:
        return (
            None if has_scope(claims, resolve_site(view_args)) else "Not authorized for this site"
        )
    if claims and claims.get("scope") == "bench":
        return None
    return "Not authorized for this bench"


def current_site_scope() -> str | None:
    """Return the ``site`` claim from the current JWT, or None."""
    claims = getattr(g, "jwt_claims", None)
    if not claims:
        return None
    return claims.get("site")
