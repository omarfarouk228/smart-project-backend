from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.state import app_state

_SETUP_ALLOWED_PATHS = (
    "/api/setup",
    "/api/organization/public",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/health",
)


class SetupMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if app_state.setup_completed:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in _SETUP_ALLOWED_PATHS):
            return await call_next(request)

        return JSONResponse(
            {"detail": "Setup required", "setup_required": True},
            status_code=503,
        )
