"""Redacted HTTP problem helpers shared by optional API routers."""

from __future__ import annotations

from typing import Any

from fastapi.responses import JSONResponse

from axcalib.api.models import Problem, ValidationIssue


class ApiProblemError(Exception):
    """Internal signal converted to a redacted problem response."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str | None = None,
        issues: tuple[ValidationIssue, ...] = (),
    ) -> None:
        super().__init__(code)
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.issues = issues


def problem_response(problem: Problem) -> JSONResponse:
    """Render a problem without reflecting rejected values or credentials."""

    headers = {"WWW-Authenticate": "Bearer"} if problem.status == 401 else None
    return JSONResponse(
        status_code=problem.status,
        content=problem.model_dump(mode="json"),
        media_type="application/problem+json",
        headers=headers,
    )


def problem_responses(*statuses: int) -> dict[int | str, dict[str, Any]]:
    """Return reusable OpenAPI response declarations for AXCalib problems."""

    return {
        status: {
            "model": Problem,
            "description": "Structured AXCalib API problem",
        }
        for status in statuses
    }


__all__ = ["ApiProblemError", "problem_response", "problem_responses"]
