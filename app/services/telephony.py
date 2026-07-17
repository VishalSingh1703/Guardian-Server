"""Telephony service layer.

Holds the call-orchestration logic, isolated from the web/transport layer
(routers) so it can be triggered, tested, or swapped without touching FastAPI.
"""

import logging
import json
from datetime import datetime
from typing import Any, Dict
from twilio.rest import Client
from fastapi import WebSocket

from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.pipeline.runner import PipelineRunner
from pipecat.transports.websocket.fastapi import FastAPIWebsocketTransport, FastAPIWebsocketParams
from pipecat.serializers.twilio import TwilioFrameSerializer
from pipecat.services.google.gemini_live.llm import GeminiLiveLLMService, GeminiLiveLLMSettings
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.frames.frames import LLMContextFrame

from app.core.config import settings
from app.core.prompts import EMERGENCY_AGENT_SYSTEM_PROMPT


# Use the uvicorn error logger to ensure logs print to the console under Uvicorn
logger = logging.getLogger("uvicorn.error")

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

    print(f"\n[DEBUG] Connecting to Twilio API to call {to_phone} from {from_phone}...\n", flush=True)
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
    
    print(f"\n[DEBUG] Twilio Call Queued! SID: {call.sid}\n", flush=True)
    logger.info(f"Call successfully queued with Twilio. SID: {call.sid}")
    return result

def initiate_call_flow(to_phone: str, from_phone: str = None) -> Dict[str, Any]:
    """
    Function called by the endpoint. Validates arguments and triggers the Twilio call.
    """
    print(f"\n[DEBUG] initiate_call_flow starting to {to_phone}...\n", flush=True)
    logger.info(f"Received request to initiate call flow to '{to_phone}'")
    
    if not from_phone:
        from_phone = settings.TWILIO_PHONE_NUMBER
        if not from_phone:
            raise ValueError("TWILIO_PHONE_NUMBER must be set in the environment or passed explicitly.")
        logger.info(f"No 'from_phone' provided. Using default Twilio number: {from_phone}")
        
    # Trigger the actual Twilio call
    call_result = make_actual_twilio_call(to_phone, from_phone)
    
    return call_result


async def run_emergency_agent(websocket: WebSocket):
    """
    WebSocket session handler for the Pipecat Gemini Live emergency agent.
    Bridges the Twilio WebSocket media stream with Gemini Multimodal Live.
    """
    print("\n[DEBUG] Starting run_emergency_agent session...\n", flush=True)
    logger.info("Initializing Pipecat Gemini Live agent...")

    if not settings.gemini_configured:
        logger.error("Gemini API key is not configured!")
        await websocket.close()
        return

    # 1. Wait for the start event from Twilio to retrieve streamSid and callSid
    stream_sid = None
    call_sid = None
    
    # Twilio sends a series of JSON messages starting with 'connected' and then 'start'
    async for message in websocket.iter_text():
        try:
            data = json.loads(message)
            if data.get("event") == "start":
                start_data = data["start"]
                stream_sid = start_data["streamSid"]
                call_sid = start_data.get("callSid")
                logger.info(f"☎️ Received Twilio start event. streamSid: {stream_sid}, callSid: {call_sid}")
                break
        except Exception as e:
            logger.error(f"Error parsing initial Twilio message: {e}")
            break

    if not stream_sid:
        logger.error("Failed to receive streamSid from Twilio handshake")
        await websocket.close()
        return

    # Initialize TwilioFrameSerializer with the extracted SIDs and credentials
    twilio_serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
        account_sid=settings.TWILIO_ACCOUNT_SID,
        auth_token=settings.TWILIO_AUTH_TOKEN
    )

    # Setup transport for Twilio WebSockets
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
            serializer=twilio_serializer,
        ),
    )

    # Initialize Gemini Live LLM Service with standard settings
    llm = GeminiLiveLLMService(
        api_key=settings.GEMINI_API_KEY,
        settings=GeminiLiveLLMService.Settings(
            model="models/gemini-2.5-flash-native-audio-preview-12-2025",
            system_instruction=EMERGENCY_AGENT_SYSTEM_PROMPT,
            voice="Puck",  # Recommended voice for emergency agent
        )
    )

    # Create the pipeline: Twilio input -> Gemini Live -> Twilio output
    pipeline = Pipeline([
        transport.input(),
        llm,
        transport.output(),
    ])

    # Initialize the runner and task
    runner = PipelineRunner()
    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=16000,
            audio_out_sample_rate=24000,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"☎️ Twilio WebSocket media stream connected! Client: {client}")
        print("\n[DEBUG] Twilio Media Stream Connected!\n", flush=True)
        # Seed the conversation context to trigger the bot to greet the caller first
        context = LLMContext(
            messages=[
                {"role": "user", "content": "Please greet the contact and explain the situation."}
            ]
        )
        await task.queue_frame(LLMContextFrame(context))

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"☎️ Twilio WebSocket media stream disconnected! Client: {client}")
        print("\n[DEBUG] Twilio Media Stream Disconnected!\n", flush=True)
        await task.cancel()

    try:
        logger.info("Running Pipecat pipeline task...")
        await runner.run(task)
    except Exception as e:
        logger.error(f"Error running emergency Pipecat agent pipeline: {str(e)}")
        print(f"\n[DEBUG] Pipeline task execution failed: {str(e)}\n", flush=True)
    finally:
        # Restore default signal handlers to prevent Ctrl+C/shutdown hangs on Windows
        import signal
        try:
            signal.signal(signal.SIGINT, signal.default_int_handler)
            signal.signal(signal.SIGTERM, signal.SIG_DFL)
        except Exception as sig_err:
            logger.warning(f"Failed to restore default signal handlers: {sig_err}")

        logger.info("Pipecat emergency agent session finished.")
        print("\n[DEBUG] run_emergency_agent session completed.\n", flush=True)

