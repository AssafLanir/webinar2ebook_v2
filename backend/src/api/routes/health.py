"""Health check endpoint."""

from fastapi import APIRouter

from src.api.response import success_response

router = APIRouter(tags=["System"])


@router.get("/health")
async def health_check() -> dict:
    """Return system health status."""
    return success_response({"status": "ok"})
