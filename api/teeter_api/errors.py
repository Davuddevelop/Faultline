"""One error shape for every failure: {"error": {"code": ..., "message": ...}}.

Messages say what went wrong and what to do about it, in the same voice as
the engine's errors, because a runner's log is read by a robotics engineer at
the worst moment of their week."""

from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def not_found(what: str) -> ApiError:
    return ApiError(404, "not_found", f"no {what} with that reference in this workspace")


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse({"error": {"code": exc.code, "message": exc.message}}, status_code=exc.status)


async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
    problems = []
    for e in exc.errors():
        loc = ".".join(str(p) for p in e.get("loc", ()) if p not in ("body",))
        problems.append(f"{loc}: {e.get('msg', 'invalid')}" if loc else e.get("msg", "invalid"))
    return JSONResponse({"error": {"code": "invalid", "message": "; ".join(problems),
                                   "problems": problems}}, status_code=422)
