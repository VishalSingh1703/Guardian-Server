"""Application factory and FastAPI instance.

Wires the app together and registers routers. Each router owns its own
endpoints, so adding a feature means adding a router here — not editing
this file's handlers.
"""

from fastapi import FastAPI

from app.routers import health, telephony


def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="Guardian AI Telephony Server",
        description="FastAPI server to orchestrate Twilio calls with Pipecat and Gemini Live",
        version="0.1.0",
    )

    app.include_router(health.router)
    app.include_router(telephony.router)

    return app


app = create_app()
