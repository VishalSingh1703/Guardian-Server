"""Request/response schemas for the telephony API."""

from pydantic import BaseModel, Field


class CallRequest(BaseModel):
    """Payload for triggering an outbound call."""

    to_phone: str = Field(
        ...,
        description="The target phone number to call (E.164 format, e.g., +1234567890)",
        examples=["+1987654321"],
    )
    from_phone: str = Field(
        None,
        description="The source phone number. If not provided, TWILIO_PHONE_NUMBER from environment is used.",
        examples=["+1234567890"],
    )
