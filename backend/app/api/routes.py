"""Core API routes."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check() -> dict[str, str]:
    """Return service health status.

    Returns:
        dict[str, str]: Health payload with status and service name.
    """
    return {"status": "ok", "service": "attentionos-backend"}
