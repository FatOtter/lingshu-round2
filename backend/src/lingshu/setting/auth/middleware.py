"""Auth Middleware: JWT validation, ContextVar injection, dev mode fallback."""

import logging
import uuid

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from lingshu.infra.context import (
    request_id_var,
    role_var,
    tenant_id_var,
    user_id_var,
)

logger = logging.getLogger(__name__)

WHITELIST_PATHS = frozenset({
    "/health",
    "/setting/v1/auth/login",
    "/setting/v1/auth/sso/config",
    "/docs",
    "/openapi.json",
    "/redoc",
})

REFRESH_PATHS = frozenset({
    "/setting/v1/auth/refresh",
})


def _error_response(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={
            "error": {"code": code, "message": message},
            "metadata": {"request_id": ""},
        },
    )


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: object, dev_mode: bool = False, **kwargs: object) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self._dev_mode = dev_mode

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        try:
            return await self._dispatch_inner(request, call_next)
        except Exception:
            logger.exception("Unhandled error in AuthMiddleware")
            return _error_response(500, "COMMON_INTERNAL_ERROR", "Internal server error")

    async def _dispatch_inner(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Set request_id for all requests
        req_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(req_id)

        path = request.url.path

        # CORS preflight: let CORSMiddleware handle it
        if request.method == "OPTIONS":
            return await call_next(request)

        # Whitelist: skip auth
        if path in WHITELIST_PATHS:
            return await call_next(request)

        # Refresh path: handled by the refresh endpoint itself
        if path in REFRESH_PATHS:
            return await call_next(request)

        # Resolve provider lazily from app.state (set during lifespan)
        provider = getattr(request.app.state, "auth_provider", None)
        if provider is None:
            return _error_response(503, "COMMON_SERVICE_UNAVAILABLE", "Service initializing")

        # Try Cookie-based JWT auth
        access_token = request.cookies.get("lingshu_access")

        if access_token:
            try:
                payload = provider.validate_token(access_token)
            except ValueError as e:
                return _error_response(401, "SETTING_AUTH_TOKEN_EXPIRED", str(e))

            # Check blacklist
            if await provider.is_revoked(payload.tid, payload.jti):
                return _error_response(401, "SETTING_AUTH_TOKEN_REVOKED", "Token has been revoked")

            user_id_var.set(payload.sub)
            tenant_id_var.set(payload.tid)
            role_var.set(payload.role)
            return await call_next(request)

        # Dev mode fallback: accept headers
        if self._dev_mode:
            user_id = request.headers.get("X-User-ID")
            tenant_id = request.headers.get("X-Tenant-ID")
            if user_id and tenant_id:
                user_id_var.set(user_id)
                tenant_id_var.set(tenant_id)
                role_var.set(request.headers.get("X-Role", "admin"))
                return await call_next(request)

        return _error_response(401, "COMMON_UNAUTHORIZED", "Authentication required")
