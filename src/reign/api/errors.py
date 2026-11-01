"""Global exception handlers — consistent JSON error shape.

Contract preserved:
- NotFoundError -> 404 {"detail": ...}
- CSVParseError -> 422 {"detail": ...}
- ValidationError/ValueError -> 400 {"detail": ...}
- Unhandled Exception -> 500 {"detail": "Internal server error"}
"""

import logging

from fastapi import Request
from fastapi.responses import JSONResponse

from reign.exceptions import AppError, CSVParseError, NotFoundError, ValidationError

logger = logging.getLogger("reign.errors")


def _detail(message: str) -> dict:
    return {"detail": message}


async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    if isinstance(exc, NotFoundError):
        return JSONResponse(status_code=404, content=_detail(str(exc)))
    if isinstance(exc, CSVParseError):
        return JSONResponse(status_code=422, content=_detail(str(exc)))
    if isinstance(exc, ValidationError):
        return JSONResponse(status_code=400, content=_detail(str(exc)))
    logger.exception("Unhandled AppError: %s", exc)
    return JSONResponse(status_code=500, content=_detail("Internal server error"))


async def value_error_handler(_request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content=_detail(str(exc)))


async def unhandled_handler(_request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error: %s", exc)
    return JSONResponse(status_code=500, content=_detail("Internal server error"))


def register_handlers(app) -> None:
    """Attach handlers; FastAPI HTTPException path stays untouched."""
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(ValueError, value_error_handler)
    app.add_exception_handler(Exception, unhandled_handler)
