"""Telephony HTTP routes.

Thin transport layer: validates the request, delegates to the service layer,
and maps failures to HTTP responses. No business logic lives here.
"""

from fastapi import APIRouter, HTTPException, status

from app.schemas.telephony import CallRequest
from app.services.telephony import initiate_call_flow

router = APIRouter(tags=["telephony"])


@router.post("/call", status_code=status.HTTP_200_OK)
async def make_call(payload: CallRequest):
    """
    Triggers an outbound call by invoking the service layer.
    """
    try:
        result = initiate_call_flow(
            to_phone=payload.to_phone,
            from_phone=payload.from_phone,
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call flow: {str(e)}",
        )
