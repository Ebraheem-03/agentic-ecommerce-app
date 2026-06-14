"""Runtime error handling — render the ONE canonical error envelope (US-E4-01).

The contract (``docs/api/contract-v0.md`` §Error catalog) says every non-2xx body is
``{"error": {"code": <ErrorCode>, "message": str, "details": ...}}`` — see
``app.schemas.envelope.ErrorResponse``. FastAPI's defaults emit ``{"detail": ...}``
instead, so this module bridges the gap:

  - ``APIError`` is the domain exception handlers raise (and ``stub()`` raises).
  - ``install_error_handlers(app)`` registers handlers that turn ``APIError``,
    Starlette ``HTTPException``, ``RequestValidationError``, and any uncaught
    ``Exception`` into the canonical envelope while preserving the HTTP status.

Messages stay plain-spoken (brand voice); internal faults never leak details.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.schemas.envelope import ErrorBody, ErrorCode, ErrorResponse

if TYPE_CHECKING:
    from fastapi import FastAPI, Request


class APIError(Exception):
    """Domain exception that maps cleanly onto the canonical error envelope.

    Raise this anywhere in a handler instead of ``HTTPException`` so the response is
    guaranteed to carry a closed ``ErrorCode`` and the contract body shape.
    """

    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


# Starlette HTTPException carries only a status + free-form detail; map the status to
# a closed ErrorCode so QA assertions stay deterministic. Anything unmapped falls back
# by status class (5xx -> internal_error, else validation_error).
_STATUS_TO_CODE: dict[int, ErrorCode] = {
    status.HTTP_400_BAD_REQUEST: ErrorCode.validation_error,
    status.HTTP_401_UNAUTHORIZED: ErrorCode.unauthenticated,
    status.HTTP_403_FORBIDDEN: ErrorCode.forbidden,
    status.HTTP_404_NOT_FOUND: ErrorCode.not_found,
    status.HTTP_409_CONFLICT: ErrorCode.conflict,
    status.HTTP_422_UNPROCESSABLE_ENTITY: ErrorCode.validation_error,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.rate_limited,
    status.HTTP_500_INTERNAL_SERVER_ERROR: ErrorCode.internal_error,
    status.HTTP_501_NOT_IMPLEMENTED: ErrorCode.not_implemented,
}

# Plain-spoken default message per code, used when the source carries none useful.
_DEFAULT_MESSAGE: dict[ErrorCode, str] = {
    ErrorCode.validation_error: "That request didn't look right.",
    ErrorCode.unauthenticated: "You need to be signed in to do that.",
    ErrorCode.forbidden: "You don't have access to that.",
    ErrorCode.not_found: "We couldn't find that.",
    ErrorCode.conflict: "That conflicts with the current state.",
    ErrorCode.rate_limited: "Too many requests — please slow down.",
    ErrorCode.internal_error: "Something went wrong on our end.",
    ErrorCode.not_implemented: "That isn't available yet.",
}


def _code_for_status(status_code: int) -> ErrorCode:
    """Map an HTTP status onto a closed ErrorCode (status-class fallback)."""
    mapped = _STATUS_TO_CODE.get(status_code)
    if mapped is not None:
        return mapped
    if status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
        return ErrorCode.internal_error
    return ErrorCode.validation_error


def _render(
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    """Serialize the canonical envelope to a JSONResponse with the given status."""
    body = ErrorResponse(error=ErrorBody(code=code, message=message, details=details))
    return JSONResponse(status_code=status_code, content=body.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    """Register the exception handlers that emit the canonical error envelope."""

    @app.exception_handler(APIError)
    async def _handle_api_error(_request: Request, exc: APIError) -> JSONResponse:
        return _render(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(
        _request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        code = _code_for_status(exc.status_code)
        # Prefer a string detail as the message; otherwise the plain default.
        message = exc.detail if isinstance(exc.detail, str) else _DEFAULT_MESSAGE[code]
        return _render(exc.status_code, code, message)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        details: dict[str, object] = {"errors": exc.errors()}
        return _render(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            ErrorCode.validation_error,
            _DEFAULT_MESSAGE[ErrorCode.validation_error],
            details,
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_request: Request, _exc: Exception) -> JSONResponse:
        # Never leak internals (message or stack) to the client.
        return _render(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            ErrorCode.internal_error,
            _DEFAULT_MESSAGE[ErrorCode.internal_error],
        )
