"""Telephony service layer.

Holds the call-orchestration logic, isolated from the web/transport layer
(routers) so it can be triggered, tested, or swapped without touching FastAPI.
"""

import logging
from datetime import datetime
from typing import Any, Dict
from twilio.rest import Client

from app.core.config import settings

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("telephony-services")

def make_actual_twilio_call(to_phone: str, from_phone: str) -> Dict[str, Any]:
    """
    Initiates an actual Twilio outbound call pointing to the server's TwiML endpoint.
    """
    account_sid = settings.TWILIO_ACCOUNT_SID
    auth_token = settings.TWILIO_AUTH_TOKEN
    server_url = settings.SERVER_URL

    if not account_sid or not auth_token:
        raise ValueError("TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in the environment.")
    
    if not server_url:
        raise ValueError("SERVER_URL must be set in the environment to serve TwiML callbacks.")

    logger.info(f"Initiating actual Twilio call from '{from_phone}' to '{to_phone}'...")
    
    client = Client(account_sid, auth_token)
    
    # Twilio will fetch the call instructions (TwiML) from this URL when answered
    twiml_url = f"{server_url}/twilio-voice"
    logger.info(f"Setting Twilio callback URL to: {twiml_url}")

    call = client.calls.create(
        to=to_phone,
        from_=from_phone,
        url=twiml_url
    )
    
    result = {
        "sid": call.sid,
        "status": call.status,
        "to": to_phone,
        "from_": from_phone,
        "date_created": datetime.utcnow().isoformat(),
        "simulation": False,
        "message": f"Twilio call initiated successfully with SID: {call.sid}"
    }
    
    logger.info(f"Call successfully queued with Twilio. SID: {call.sid}")
    return result

def initiate_call_flow(to_phone: str, from_phone: str = None) -> Dict[str, Any]:
    """
    Function called by the endpoint. Validates arguments and triggers the Twilio call.
    """
    logger.info(f"Received request to initiate call flow to '{to_phone}'")
    
    if not from_phone:
        from_phone = settings.TWILIO_PHONE_NUMBER
        if not from_phone:
            raise ValueError("TWILIO_PHONE_NUMBER must be set in the environment or passed explicitly.")
        logger.info(f"No 'from_phone' provided. Using default Twilio number: {from_phone}")
        
    # Trigger the actual Twilio call
    call_result = make_actual_twilio_call(to_phone, from_phone)
    
    return call_result
