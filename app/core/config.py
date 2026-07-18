"""Centralized application configuration.

Single source of truth for every environment-driven value. All other modules
read settings from here instead of calling ``os.getenv`` directly (DRY) — env
keys and their defaults are declared exactly once.
"""

import os

from dotenv import load_dotenv

# Load variables from a local .env once, at import time, for the whole app.
load_dotenv(override=True)

# Placeholder value shipped in .env.example; used to detect an unconfigured account.
_UNCONFIGURED_TWILIO_SID = "your_twilio_account_sid_here"


class Settings:
    """Typed accessors for the server's environment configuration."""

    # --- Server ---
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", 8000))
    # Base URL Twilio uses for webhook / TwiML callbacks.
    SERVER_URL: str = os.getenv("SERVER_URL", "https://your-ngrok-subdomain.ngrok-free.app")

    # --- Twilio ---
    TWILIO_ACCOUNT_SID: str | None = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: str | None = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "+1234567890")

    # --- Gemini / Pipecat ---
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
    VISION_CONFIDENCE_THRESHOLD: float = float(os.getenv("VISION_CONFIDENCE_THRESHOLD", "0.80"))

    @property
    def twilio_configured(self) -> bool:
        """True once the Twilio account SID has been set to a real value."""
        return self.TWILIO_ACCOUNT_SID not in [None, "", _UNCONFIGURED_TWILIO_SID]

    @property
    def gemini_configured(self) -> bool:
        """True once the Gemini API key has been set to a real value."""
        return self.GEMINI_API_KEY not in [None, ""]



# Import this shared instance everywhere: ``from app.core.config import settings``.
settings = Settings()
