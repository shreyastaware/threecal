import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers
        super().__init__(message)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        logger.error(
            "application error",
            extra={"code": exc.code, "status": exc.status_code, "path": request.url.path},
            exc_info=exc,
        )
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message, "code": exc.code},
        headers=exc.headers,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Last-resort handler: log with traceback (Sentry also captures it) and hide internals from clients.
    logger.exception(
        "unhandled exception",
        extra={"method": request.method, "path": request.url.path},
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Something went wrong. Please try again.", "code": "internal_error"},
    )


class UnhandledExceptionMiddleware:
    """Turns unexpected errors into the JSON 500 inside the CORS middleware.

    Starlette sends responses for unhandled exceptions from its outermost error
    middleware, which bypasses CORS, so browsers reported them as "Failed to fetch".
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        response_started = False

        async def tracking_send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, tracking_send)
        except Exception as exc:
            if response_started:
                raise
            response = await unhandled_exception_handler(Request(scope), exc)
            await response(scope, receive, send)
