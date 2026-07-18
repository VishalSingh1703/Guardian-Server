"""Application factory and FastAPI instance.

Wires the app together and registers routers. Each router owns its own
endpoints, so adding a feature means adding a router here — not editing
this file's handlers.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.routers import health, telephony, vision


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Guardian AI Telephony Server",
        description="FastAPI server to orchestrate Twilio calls with Pipecat and Gemini Live",
        version="0.1.0",
    )

    # Allow the browser-based Webapp (a different origin) to call this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=False,  # no cookies; tokens travel in the request body
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)
    app.include_router(telephony.router)
    app.include_router(vision.router)

    return app


app = create_app()
