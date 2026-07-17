"""Telephony service layer.

Holds the call-orchestration logic, isolated from the web/transport layer
(routers) so it can be triggered, tested, or swapped without touching FastAPI.
"""

# ── stdlib ────────────────────────────────────────────────────────────────────
import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

# ── third-party ───────────────────────────────────────────────────────────────
from loguru import logger
from twilio.rest import Client
from fastapi import WebSocket

# ── pipecat: pipeline & transport ─────────────────────────────────────────────
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.serializers.twilio import TwilioFrameSerializer

# ── pipecat: LLM & audio ─────────────────────────────────────────────────────
from pipecat.services.google.gemini_live.llm import (
    GeminiLiveLLMService,
    InputParams,
    GeminiModalities,
)
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair
from pipecat.transcriptions.language import Language

# ── pipecat: tools, frames & processors ───────────────────────────────────────
from pipecat.adapters.schemas.function_schema import FunctionSchema
from pipecat.adapters.schemas.tools_schema import ToolsSchema
from pipecat.services.llm_service import FunctionCallParams
from pipecat.frames.frames import EndTaskFrame, LLMRunFrame, TTSSpeakFrame
from pipecat.processors.frame_processor import FrameDirection



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


# async def run_emergency_agent(websocket: WebSocket):
#     """
#     WebSocket session handler for the Pipecat Gemini Live emergency agent.
#     Bridges the Twilio WebSocket media stream with Gemini Multimodal Live.
#     """
#     print("\n[DEBUG] Starting run_emergency_agent session...\n", flush=True)
#     logger.info("Initializing Pipecat Gemini Live agent...")

#     if not settings.gemini_configured:
#         logger.error("Gemini API key is not configured!")
#         await websocket.close()
#         return

#     # 1. Wait for the start event from Twilio to retrieve streamSid and callSid
#     stream_sid = None
#     call_sid = None
    
#     # Twilio sends a series of JSON messages starting with 'connected' and then 'start'
#     async for message in websocket.iter_text():
#         try:
#             data = json.loads(message)
#             if data.get("event") == "start":
#                 start_data = data["start"]
#                 stream_sid = start_data["streamSid"]
#                 call_sid = start_data.get("callSid")
#                 logger.info(f"☎️ Received Twilio start event. streamSid: {stream_sid}, callSid: {call_sid}")
#                 break
#         except Exception as e:
#             logger.error(f"Error parsing initial Twilio message: {e}")
#             break

#     if not stream_sid:
#         logger.error("Failed to receive streamSid from Twilio handshake")
#         await websocket.close()
#         return

#     # Initialize TwilioFrameSerializer with the extracted SIDs and credentials
#     twilio_serializer = TwilioFrameSerializer(
#         stream_sid=stream_sid,
#         call_sid=call_sid,
#         account_sid=settings.TWILIO_ACCOUNT_SID,
#         auth_token=settings.TWILIO_AUTH_TOKEN
#     )

#     # Setup transport for Twilio WebSockets
#     transport = FastAPIWebsocketTransport(
#         websocket=websocket,
#         params=FastAPIWebsocketParams(
#             audio_in_enabled=True,
#             audio_out_enabled=True,
#             audio_in_sample_rate=8000,
#             audio_out_sample_rate=8000,
#             serializer=twilio_serializer,
#         ),
#     )

#     # Prepend 'models/' prefix to settings.GEMINI_MODEL if not present
#     model_name = settings.GEMINI_MODEL
#     if not model_name.startswith("models/"):
#         model_name = f"models/{model_name}"

#     # Initialize Gemini Live LLM Service
#     llm = GeminiLiveLLMService(
#         api_key=settings.GEMINI_API_KEY,
#         settings=GeminiLiveLLMService.Settings(
#             model=model_name,
#             voice="Puck",
#             system_instruction=EMERGENCY_AGENT_SYSTEM_PROMPT,
#         ),
#     )

#     # Create context (empty) and aggregator pair with local VAD for turn detection
#     context = LLMContext()
#     user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
#         context,
#         realtime_service_mode=True,
#         user_params=LLMUserAggregatorParams(
#             vad_analyzer=SileroVADAnalyzer(),
#         ),
#     )

#     # Build the pipeline
#     pipeline = Pipeline([
#         transport.input(),
#         user_aggregator,
#         llm,
#         transport.output(),
#         assistant_aggregator,
#     ])

#     worker = PipelineWorker(
#         pipeline,
#         params=PipelineParams(
#             enable_metrics=True,
#             enable_usage_metrics=True,
#         ),
#     )

#     @transport.event_handler("on_client_connected")
#     async def on_client_connected(transport, client):
#         logger.info(f"☎️ Twilio WebSocket media stream connected! Client: {client}")
#         # Kick off the conversation: add a developer message and send LLMRunFrame
#         context.add_message(
#             {
#                 "role": "developer",
#                 "content": "Please greet the contact and explain the emergency situation.",
#             }
#         )
#         await worker.queue_frames([LLMRunFrame()])

#     @transport.event_handler("on_client_disconnected")
#     async def on_client_disconnected(transport, client):
#         logger.info(f"☎️ Twilio WebSocket media stream disconnected! Client: {client}")
#         await worker.cancel()

#     try:
#         logger.info("Running Pipecat pipeline...")
#         runner = WorkerRunner(handle_sigint=False)
#         await runner.add_workers(worker)
#         await runner.run()
#     except Exception as e:
#         logger.error(f"Error running emergency Pipecat agent pipeline: {str(e)}")
#     finally:
#         logger.info("Pipecat emergency agent session finished.")




async def terminate_call(params: FunctionCallParams):
    logger.info("calling terminate_call function")
    await params.result_callback(
        {"status": "call_ended", "message": "The conversation has ended."}
    )
    await params.llm.push_frame(EndTaskFrame(), FrameDirection.UPSTREAM)


async def run_agent_live_gemini_twilio(
    websocket: WebSocket,
    api_key: str,
    model: str = "gemini-2.0-flash-live-001",
    voice: Optional[str] = "Aoede",
    language: str = "en-US",
    greeting_text: Optional[str] = None,
    system_instruction: Optional[str] = None,
    dynamic_instruction: Optional[str] = None,
):
    """Low-latency realtime voice agent: Gemini Live (AI Studio API) + Twilio Media Streams."""
    if not api_key:
        api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Google/Gemini API key is required for AI Studio")

    language_map = {
        "en-US": Language.EN_US, "en-IN": Language.EN_IN, "en-GB": Language.EN_GB,
        "hi-IN": Language.HI_IN, "bn-IN": Language.BN_IN, "gu-IN": Language.GU_IN,
        "kn-IN": Language.KN_IN, "ml-IN": Language.ML_IN, "mr-IN": Language.MR_IN,
        "ta-IN": Language.TA_IN, "te-IN": Language.TE_IN,
    }
    pipecat_language = language_map.get(language, Language.EN_US)

    # Twilio handshake: consume "connected" then "start" to grab streamSid + callSid
    connected_msg = await websocket.receive_json()
    logger.info(f"Twilio connected: {connected_msg}")
    if connected_msg.get("event") != "connected":
        await websocket.close(code=1000)
        return

    start_msg = await websocket.receive_json()
    logger.info(f"Twilio start: {start_msg}")
    if start_msg.get("event") != "start":
        await websocket.close(code=1000)
        return

    stream_sid = start_msg["start"]["streamSid"]
    call_sid = start_msg["start"].get("callSid")

    serializer = TwilioFrameSerializer(
        stream_sid=stream_sid,
        call_sid=call_sid,
        account_sid=os.getenv("TWILIO_ACCOUNT_SID"),
        auth_token=os.getenv("TWILIO_AUTH_TOKEN"),
    )

    vad_analyzer = SileroVADAnalyzer(
        sample_rate=8000,
        params=VADParams(confidence=0.7, start_secs=0.2, stop_secs=0.5),
    )

    transport = FastAPIWebsocketTransport(
        websocket,
        params=FastAPIWebsocketParams(
            serializer=serializer,
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            vad_analyzer=vad_analyzer,
            vad_enabled=True,
            vad_audio_passthrough=True,
        ),
    )

    tools = ToolsSchema(standard_tools=[
        FunctionSchema(
            name="terminate_call",
            description=(
                "Ends the voice call permanently. ONLY use when the user "
                "explicitly asks to end the call (e.g., 'goodbye', 'hang up', "
                "'end the call') or confirms they have no more questions."
            ),
            properties={},
            required=[],
        )
    ])

    llm = GeminiLiveLLMService(
        api_key=api_key,
        model=f"models/{model}",
        voice_id=voice or "Aoede",
        system_instruction=system_instruction or "",
        tools=tools,
        transcribe_model_audio=True,
        params=InputParams(language=pipecat_language, modalities=GeminiModalities.AUDIO),
    )
    llm.register_function("terminate_call", terminate_call)

    initial_messages = []
    if dynamic_instruction:
        initial_messages.append({"role": "user", "content": dynamic_instruction})
    context_aggregator = LLMContextAggregatorPair(LLMContext(messages=initial_messages))

    pipeline = Pipeline([
        transport.input(),
        context_aggregator.user(),
        llm,
        transport.output(),
        context_aggregator.assistant(),
    ])

    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True, enable_usage_metrics=True),
    )

    async def enforce_hard_limit(t: PipelineTask, seconds: int = 360):
        await asyncio.sleep(seconds)
        logger.info(f"Forcefully terminating call after {seconds} seconds.")
        await t.cancel()

    timeout_handle = asyncio.create_task(enforce_hard_limit(task, 360))

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info("Twilio client connected")
        if greeting_text:
            await task.queue_frame(TTSSpeakFrame(greeting_text))
        await task.queue_frames([LLMRunFrame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info("Twilio client disconnected")
        await task.cancel()

    try:
        await PipelineRunner(handle_sigint=False).run(task)
    finally:
        timeout_handle.cancel()
