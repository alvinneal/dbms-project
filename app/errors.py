# One error shape for the whole API, which is what a frontend wants to rely on:
#   {"detail": "human readable message", "errors": [{"field": "...", "message": "..."}]}
# `errors` is only present for request validation failures (422).
#
# Status codes: 404 not found, 409 conflicts and business-rule rejections
# (duplicate, overlapping booking, wrong state), 422 invalid input.
import logging
import re

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, InternalError, OperationalError
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("app")

UNIQUE, FOREIGN_KEY, NOT_NULL, CHECK = "23505", "23503", "23502", "23514"


def _reply(status: int, detail: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=status, content={"detail": detail, **extra})


def _pretty(name: str) -> str:
    return name.replace("_", " ")


def integrity_message(exc: IntegrityError) -> tuple[int, str]:
    diag = exc.orig.diag
    code = exc.orig.pgcode
    detail = diag.message_detail or ""
    table = _pretty(diag.table_name or "record")

    if code == UNIQUE:
        m = re.search(r"Key \((.+?)\)=\((.*?)\) already exists", detail)
        if m:
            return 409, f"A {table} with {_pretty(m.group(1))} '{m.group(2)}' already exists"
        return 409, f"That {table} already exists"
    if code == FOREIGN_KEY:
        m = re.search(r'Key \((.+?)\)=\((.*?)\) is not present in table "(.+?)"', detail)
        if m:
            return 422, f"{_pretty(m.group(3)).capitalize()} {m.group(2)} does not exist"
        m = re.search(r'is still referenced from table "(.+?)"', detail)
        if m:
            return 409, f"This {table} cannot be deleted because {_pretty(m.group(1))} records still refer to it"
        return 409, "This record is linked to other records"
    if code == NOT_NULL:
        return 422, f"{_pretty(diag.column_name or 'a field')} is required"
    if code == CHECK:
        return 422, f"Value rejected by rule '{diag.constraint_name}'"
    return 409, diag.message_primary or "The change conflicts with existing data"


def install(app: FastAPI) -> None:
    @app.exception_handler(IntegrityError)
    async def _integrity(request: Request, exc: IntegrityError):
        return _reply(*integrity_message(exc))

    # RAISE EXCEPTION in the procedures/triggers arrives as InternalError:
    # the message is the business rule that was broken.
    @app.exception_handler(InternalError)
    async def _rule(request: Request, exc: InternalError):
        diag = getattr(exc.orig, "diag", None)
        return _reply(409, getattr(diag, "message_primary", None) or str(exc.orig).splitlines()[0])

    @app.exception_handler(DataError)
    async def _data(request: Request, exc: DataError):
        diag = getattr(exc.orig, "diag", None)
        return _reply(422, getattr(diag, "message_primary", None) or "Invalid value")

    @app.exception_handler(OperationalError)
    async def _down(request: Request, exc: OperationalError):
        log.error("database unavailable: %s", exc.orig)
        return _reply(503, "The database is unavailable, try again shortly")

    @app.exception_handler(RequestValidationError)
    async def _invalid(request: Request, exc: RequestValidationError):
        errors = []
        for e in exc.errors():
            loc = [str(p) for p in e["loc"] if p not in ("body", "query", "path")]
            msg = e["msg"].removeprefix("Value error, ")
            errors.append({"field": ".".join(loc) or "body", "message": msg})
        summary = "; ".join(f"{e['field']}: {e['message']}" for e in errors)
        return _reply(422, f"Invalid input - {summary}", errors=errors)

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail},
                            headers=getattr(exc, "headers", None))

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled error on %s %s", request.method, request.url.path)
        return _reply(500, "Something went wrong on our side")
