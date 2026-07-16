import os
import uuid
import logging
from datetime import datetime
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telephony-services")

def dummy_make_twilio_call(to_phone: str, from_phone: str) -> Dict[str, Any]:
    """
    Dummy function that simulates making a Twilio outbound call configured to use
    Pipecat and Gemini Live.
    """
    logger.info(f"[SIMULATION] Initiating Twilio call from '{from_phone}' to '{to_phone}'...")
    
    # Simulate loading server url for Twilio webhook callback / TwiML
    server_url = os.getenv("SERVER_URL", "https://your-ngrok-subdomain.ngrok-free.app")
    logger.info(f"[SIMULATION] Twilio will fetch TwiML instructions from: {server_url}/twilio-voice")
    logger.info(f"[SIMULATION] Pipecat WebRTC / WebSocket agent endpoint: ws://{server_url.split('://')[-1]}/ws")
    logger.info("[SIMULATION] Connecting Pipecat agent pipeline with Gemini Live model backend...")
    
    mock_sid = f"CA{uuid.uuid4().hex}"
    
    result = {
        "sid": mock_sid,
        "status": "queued",
        "to": to_phone,
        "from_": from_phone,
        "date_created": datetime.utcnow().isoformat(),
        "simulation": True,
        "message": "Dummy Twilio Pipecat call initiated successfully (Simulated)."
    }
    
    logger.info(f"[SIMULATION] Call queued successfully with mock SID: {mock_sid}")
    return result

def initiate_call_flow(to_phone: str, from_phone: str = None) -> Dict[str, Any]:
    """
    Function called by the endpoint. Validates arguments and triggers the dummy call.
    """
    logger.info(f"Received request to initiate call flow to '{to_phone}'")
    
    if not from_phone:
        from_phone = os.getenv("TWILIO_PHONE_NUMBER", "+1234567890")
        logger.info(f"No 'from_phone' provided. Using default Twilio number: {from_phone}")
        
    # Trigger the dummy function
    call_result = dummy_make_twilio_call(to_phone, from_phone)
    
    return call_result
