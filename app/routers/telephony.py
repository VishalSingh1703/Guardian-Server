"""Telephony HTTP routes.

Thin transport layer: validates the request, delegates to the service layer,
and maps failures to HTTP responses. No business logic lives here.
"""

import logging
from fastapi import APIRouter, HTTPException, status, Response, Request, WebSocket
from app.core.config import settings
from app.schemas.telephony import CallRequest
from app.core.prompts import EMERGENCY_AGENT_SYSTEM_PROMPT
from app.services.telephony import (
    initiate_call_flow,
    run_agent_live_gemini_twilio,
    run_agent_sarvam_gemini_murf_twilio,
)

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
    Logs incoming Twilio request parameters and returns TwiML instructions
    to connect to our WebSocket audio stream.
    """
    # Direct print statement to guarantee console output
    print("\n[DEBUG] ===> /twilio-voice webhook endpoint hit! <===\n", flush=True)
    
    # Parse form data parameters sent by Twilio
    call_sid = "unknown"
    call_status = "unknown"
    direction = "unknown"
    
    try:
        form_data = await request.form()
        call_sid = form_data.get("CallSid", "unknown")
        call_status = form_data.get("CallStatus", "unknown")
        direction = form_data.get("Direction", "unknown")
        logger.info(f"☎️ Twilio Webhook triggered! CallSid: {call_sid} | Status: {call_status} | Direction: {direction}")
    except Exception as e:
        logger.warning(f"Could not parse form data from Twilio: {str(e)}")

    # Resolve websocket URL based on configured SERVER_URL
    server_url = settings.SERVER_URL
    if server_url.startswith("https://"):
        websocket_url = server_url.replace("https://", "wss://") + "/ws"
    elif server_url.startswith("http://"):
        websocket_url = server_url.replace("http://", "ws://") + "/ws"
    else:
        websocket_url = f"wss://{server_url}/ws"

    logger.info(f"Connecting Twilio CallSid {call_sid} to WebSocket Stream: {websocket_url}")

    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{websocket_url}" />
    </Connect>
</Response>"""
    return Response(content=twiml_response, media_type="application/xml")


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket connection point for Twilio Media Streams.
    Spins up the Pipecat Gemini Live real-time audio pipeline.
    """
    print("\n[DEBUG] WebSocket /ws upgrade requested by client...\n", flush=True)
    await websocket.accept()
    agent_type = (settings.AGENT_TYPE or "gemini_live").lower()
    logger.info(f"Dispatching /ws to agent: {agent_type}")
    try:
        if agent_type == "sarvam":
            await run_agent_sarvam_gemini_murf_twilio(
                websocket,
                gemini_api_key=settings.GEMINI_API_KEY,
                sarvam_api_key=settings.SARVAM_API_KEY,
                murf_api_key=settings.MURF_API_KEY,
                model=settings.SARVAM_AGENT_LLM_MODEL,
                language=settings.AGENT_LANGUAGE,
                system_instruction=EMERGENCY_AGENT_SYSTEM_PROMPT,
            )
        else:
            await run_agent_live_gemini_twilio(
                websocket,
                api_key=settings.GEMINI_API_KEY,
                model=settings.GEMINI_MODEL,
                system_instruction=EMERGENCY_AGENT_SYSTEM_PROMPT,
            )
    except Exception as e:
        logger.error(f"WebSocket error in /ws: {str(e)}")
        print(f"\n[DEBUG] WebSocket route error: {str(e)}\n", flush=True)

