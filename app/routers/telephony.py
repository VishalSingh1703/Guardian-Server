"""Telephony HTTP routes.

Thin transport layer: validates the request, delegates to the service layer,
and maps failures to HTTP responses. No business logic lives here.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Response, Request

from app.schemas.telephony import CallRequest
from app.services.telephony import initiate_call_flow

router = APIRouter(tags=["telephony"])
logger = logging.getLogger("uvicorn.error")


@router.post("/call", status_code=status.HTTP_200_OK)
async def make_call(payload: CallRequest):
    """
    Triggers an outbound call by invoking the service layer.
    """
    # Direct print statement to guarantee console output
    print(f"\n[DEBUG] ===> /call endpoint hit! to_phone={payload.to_phone} <===\n", flush=True)
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

@router.api_route("/twilio-voice", methods=["GET", "POST"])
async def twilio_voice(request: Request):
    """
    Endpoint that Twilio requests when the call is answered.
    Logs incoming Twilio request parameters and returns TwiML instructions.
    """
    # Direct print statement to guarantee console output
    print("\n[DEBUG] ===> /twilio-voice webhook endpoint hit! <===\n", flush=True)
    
    # Parse form data parameters sent by Twilio
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "unknown")
        call_status = form_data.get("CallStatus", "unknown")
        direction = form_data.get("Direction", "unknown")
        logger.info(f"☎️ Twilio Webhook triggered! CallSid: {call_sid} | Status: {call_status} | Direction: {direction}")
    except Exception as e:
        logger.warning(f"Could not parse form data from Twilio: {str(e)}")

    twiml_response = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">Hello! This is a test call from the Guardian AI telephony server. The call is successfully connected, and no AI engine is active at the moment.</Say>
    <Pause length="2"/>
    <Say>Thank you for testing, goodbye!</Say>
    <Hangup/>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")
