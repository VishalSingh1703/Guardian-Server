"""Health / readiness endpoints."""

from fastapi import APIRouter, status

from app.core.config import settings

router = APIRouter(tags=["health"])


@router.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint to ensure server is running.
    """
    return {
        "status": "online",
        "server": "Guardian AI Telephony Temp Server",
        "configs_loaded": {
            "twilio_configured": settings.twilio_configured,
            "server_url": settings.SERVER_URL,
        },
    }
