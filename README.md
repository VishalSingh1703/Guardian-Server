# Guardian-Server

Backend & integration hub for the **Guardian** platform — AI-powered digital vehicle identity and emergency response. Both clients (`Guardian-App`, `Guardian-Webapp`) talk to this server exclusively via HTTP API.

See [`CLAUDE.md`](./CLAUDE.md) for full architecture context and invariants.

---

## Project Structure

```
run.py                        # local dev entrypoint (python run.py)
app/
  main.py                     # create_app() — builds FastAPI app, registers routers
  core/
    config.py                 # Settings singleton — all env vars live here
    prompts.py                # System prompts for telephony agent
  schemas/
    telephony.py              # Pydantic models for telephony
  routers/
    health.py                 # GET /  — health check
    telephony.py              # POST /call, GET+POST /twilio-voice, WS /ws
    vision.py                 # Vision endpoints (plate + damage)
  services/
    telephony.py              # Twilio call orchestration + Pipecat Gemini Live agent
  vision/                     # Isolated vision module
    README.md                 # Vision-specific docs
    interface.py              # Abstract VisionProvider base class
    models.py                 # DamageAnalysisResult schema
    plate_models.py           # PlateVerificationResult, UnifiedVerificationResult schemas
    prompts.py                # Damage detection system prompt
    plate_prompts.py          # Plate extraction system prompt
    service.py                # VisionService (damage analysis)
    plate_service.py          # PlateVerificationService (plate matching)
    providers/
      gemini.py               # GeminiVisionProvider (google-genai async SDK)
```

**Layered architecture:** `routers` (HTTP transport only) → `services`/`vision` (business logic) → `core/config` (env). Add a feature by adding a router + service pair and registering the router in `app/main.py`.

---

## Getting Started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # fill in GEMINI_API_KEY, Twilio credentials, etc.
python run.py               # server starts on http://localhost:8000
```

Interactive API docs available at [`/docs`](http://localhost:8000/docs).

---

## Current Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/` | Health check + config status |
| `POST` | `/call` | Trigger outbound Twilio call |
| `GET/POST` | `/twilio-voice` | TwiML callback for IVR |
| `WS` | `/ws` | WebSocket for Pipecat Gemini Live voice agent |
| `POST` | `/vision/verify-incident` | **Unified** plate + damage verification pipeline |
| `POST` | `/vision/plate/verify` | Plate verification via photo (Gemini OCR) |
| `POST` | `/vision/plate/verify-manual` | Plate verification via manual text entry |
| `POST` | `/vision/webapp/analyze` | Standalone structural damage detection |

See [`app/vision/README.md`](./app/vision/README.md) for full vision API docs.

---

## Environment Variables

```env
# Server
HOST=0.0.0.0
PORT=8000
SERVER_URL=https://your-ngrok-url.ngrok-free.app

# Twilio
TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_PHONE_NUMBER=+1234567890

# Gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.1-flash-lite
VISION_CONFIDENCE_THRESHOLD=0.80
```

> **Gemini model note:** With a free-tier API key, use `gemini-3.1-flash-lite`. Models `gemini-2.5-flash` and `gemini-1.5-flash` return 404 for new keys.

---

## What's Not Yet Built

- PostgreSQL database + SQLAlchemy models + Alembic migrations
- Vehicle registration (`POST /vehicles/register`) with AES-GCM encrypted PII
- QR-based OCR resolution (`POST /ocr/resolve`) — currently `registered_plate` is passed directly by the client
- Owner crash self-report (`POST /crash/self-report`) with g-force + GPS
- Firebase FCM push notifications
- Redis-backed rate limiting + cooldowns
- Auth (OTP flow)
