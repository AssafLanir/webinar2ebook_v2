"""Response envelope helpers for consistent API responses."""

from typing import Any, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ErrorDetail(BaseModel):
    """Error detail structure."""

    code: str
    message: str


class ApiResponse(BaseModel):
    """Standard API response envelope."""

    data: Any | None = None
    error: ErrorDetail | None = None


def success_response(data: Any) -> dict[str, Any]:
    """Create a success response envelope."""
    return {"data": data, "error": None}


def error_response(code: str, message: str) -> dict[str, Any]:
    """Create an error response envelope."""
    return {"data": None, "error": {"code": code, "message": message}}
