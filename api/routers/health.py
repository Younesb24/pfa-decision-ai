"""Health check endpoint."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health_check() -> dict:
    """Simple health check for container orchestration."""
    return {"status": "healthy", "service": "pfa-decision-ai"}
