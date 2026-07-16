# Guardian-Server — Backend & Integration Hub

> Part of the **Guardian** platform (AI-powered digital vehicle identity & emergency response). Read the platform-wide PRD for full product context; this file covers **only this repository**. This is the **brain** of the system: both clients (`Guardian-App`, `Guardian-Webapp`) integrate with the platform *exclusively* through this server's HTTP API. There is no other integration point.

- **Repo:** `github.com/VishalSingh1703/Guardian-Server`
- **Consumers:** `Guardian-App` (Kotlin owner/driver client) · `Guardian-Webapp` (Next.js bystander client).
- **Status:** greenfield — the repo is effectively empty. This document defines what to build.

---

## 1. What this component IS
Everything backend. This server owns:
1. **OCR engine** — parse a license plate from an uploaded camera frame, uppercase it, and compute `SHA256(plate)`. Plate hashing is **authoritative here** — never trust a client-computed hash.
2. **AI contextual verification (anti-abuse)** — a computer-vision pipeline that confirms real structural vehicle damage/impact in a wide frame before any alert can fire. This is the gate that stops malicious/accidental panic alerts.
3. **Privacy-preserving profile store** — PostgreSQL holding vehicle profiles keyed by `identity_hash`, with PII **AES-GCM-encrypted at rest** and only a binary `active_profile` + masked route tokens ever exposed to bystanders.
4. **Telephony / Voice AI layer (Twilio)** — parallel SMS + automated IVR voice broadcast to emergency contacts, with TTS prompts, DTMF handling (press 1 / press 2), and a retry loop up to `ivr_retry_limit`.
5. **Geofencing & rate limiting** — proximity validation of the scanning device and throttling/isolation of abusive client nodes.
6. **Push fan-out (FCM)** — courtesy alerts (parking/vandalism/fleet) to the owner's App.

## 2. What this component is NOT
- ❌ Not a UI. No rendered pages here (bystander UI is the Webapp; owner UI is the App).
- ❌ Not a place for client secrets to leak *out*. Bystanders receive `active_profile`, an `incident_token`, and (post-verification) the `medical_passport` block only — never names, phones, or insurance refs.

---

## 3. Recommended tech stack
Chosen to fit the AI/CV/OCR + telephony workload:
- **Runtime:** Python 3.11+ · **FastAPI** + **Uvicorn** (async, typed, OpenAPI out of the box).
- **Validation:** Pydantic v2 models for every request/response (they *are* the API contract).
- **DB:** PostgreSQL + SQLAlchemy 2.x (async) + Alembic migrations.
- **AI verification:** **Anthropic Python SDK** (`anthropic`) for vision-based damage confirmation; the latest Claude models are the default choice for the CV/anti-abuse gate.
- **OCR / CV:** OpenCV for frame handling; EasyOCR or Tesseract for plate text (or a cloud OCR API — abstract it behind an interface so it's swappable).
- **Telephony/Voice AI:** **Twilio Python SDK** — Programmable SMS + Programmable Voice (TwiML for IVR, `<Gather>` for DTMF, `<Say>`/TTS for prompts).
- **Crypto:** `cryptography` (`AESGCM` for PII at rest, `hashlib.sha256` for plate identity).
- **Push:** Firebase Admin SDK (FCM) for owner courtesy alerts.
- **Rate limiting:** Redis-backed (e.g. `slowapi` or a custom token-bucket) for node throttling + cooldowns.

### Current layout (what exists today)
Organized into a layered package: **routers** (transport) → **services** (business logic) → **core/config** (env). Add new features by adding a router + service pair and registering the router in `app/main.py` — never by fattening existing handlers.
```
run.py                    # local dev entrypoint (python run.py)
app/
  main.py                 # create_app() — builds FastAPI, registers routers
  core/
    config.py             # Settings: single source of truth for all env vars
  schemas/
    telephony.py          # Pydantic request/response models
  routers/
    health.py             # GET /
    telephony.py          # POST /call (thin: validates + delegates to service)
  services/
    telephony.py          # call-flow orchestration + (dummy) Twilio integration
```

### Planned modules (add only when the feature lands — YAGNI, don't scaffold empty)
```
app/core/security.py      # AES-GCM encrypt/decrypt, SHA256 plate hashing
app/db/                   # SQLAlchemy models, session, Alembic
app/services/ocr.py       # plate frame -> uppercase string -> SHA256
app/services/vision.py    # AI damage verification (anti-abuse gate)
app/services/geofence.py  # proximity validation
app/services/push.py      # FCM courtesy alerts
app/routers/auth.py · vehicles.py · incidents.py · utilities.py · webhooks.py
```

---

## 4. The API this server MUST expose
Full contract in the platform PRD §6. This server owns and versions it; a change here is a breaking change for both clients and must be announced. All routes under `/api/v1`; image frames are `multipart/form-data`.

**Owner/driver (Guardian-App):**
- `POST /auth/request-otp`, `POST /auth/verify-otp` — phone OTP auth.
- `POST /vehicles/register` — receive **raw plate + plaintext PII**; hash the plate, AES-GCM-encrypt PII, store keyed by `identity_hash`.
- `GET`/`PUT /vehicles/me` — profile & medical-passport CRUD.
- `POST /devices/push-token` — store FCM token.
- `POST /crash/self-report` — `{ gForce, gps, timestamp }` → enter broadcast pipeline (§3.1 steps 4–5).
- `GET /alerts` — owner's inbound courtesy alerts.

**Bystander (Guardian-Webapp):**
- `POST /ocr/resolve` — frame → OCR → hash → lookup → `{ active_profile, incident_token }`. **No PII.**
- `POST /incidents/{token}/verify` — wide damage frame + GPS → CV gate + geofence → `{ verified, alert_unlocked }`.
- `POST /incidents/{token}/trigger-emergency` — fire SMS + IVR. **Idempotent per token.** Reject if not `verified`.
- `GET /incidents/{token}/medical-passport` — return the `medical_passport` block **only**, and **only** after verification.
- `POST /utilities/parking` · `/utilities/vandalism` · `/utilities/fleet` — secondary alerts; enforce cooldown (parking = 5 min) + rate limits.

**Twilio webhooks (internal):**
- `POST /webhooks/twilio/voice` — TwiML for the IVR loop; DTMF `1` = bridge encrypted line, `2` = send navigation coordinates.
- `POST /webhooks/twilio/status` — answer/delivery callbacks; drive retries up to `ivr_retry_limit`.

---

## 5. Data model (canonical)
Store per the platform PRD §5 `vehicle_profile` schema. Key points:
- Primary key / lookup key = `identity_hash` (`SHA256` of the uppercased plate). Index it.
- `encrypted_metadata` (owner_name, primary_phone, insurance_policy_ref) → **AES-GCM ciphertext columns**, never plaintext at rest.
- `emergency_contacts[]` → `{ contact_priority, phone_proxy_target, ivr_retry_limit }`, ordered by priority for the IVR loop.
- `medical_passport` → the **only** block ever disclosed to a bystander (blood_group, allergies[], organ_donor).
- Add: incident records (token, plate hash, gps, verification state, timestamps), rate-limit/cooldown state, audit log of triggers.

---

## 6. Non-negotiable invariants (this server enforces them for the whole platform)
1. **PII never reaches a bystander** — bystander responses carry `active_profile` / `incident_token` / `medical_passport` only.
2. **Plate hash is authoritative here** — compute `SHA256` server-side; ignore any client hash.
3. **No alert without visual verification** — `trigger-emergency` must 4xx unless the incident is `verified` (CV gate + geofence passed).
4. **AES-GCM at rest**, with the key from env/secret manager — **never** commit the key or any Twilio/Anthropic/Firebase credential.
5. **This server is the sole integration point** — clients never call Twilio/OCR/AI vendors; only this server does.
6. **Rate limits & cooldowns enforced here** (parking 5-min cooldown, per-node scan throttling, abusive-node isolation) regardless of client behavior.

---

## 7. Working conventions
- Every endpoint gets typed Pydantic request/response models — the generated OpenAPI schema is the coordination artifact for the App and Webapp teams.
- Keep vendor integrations (OCR, vision, telephony, push) behind `services/` interfaces so they're swappable and testable without live API calls.
- Secrets via env only; provide a `.env.example` (committed) and keep `.env` gitignored.
- Long-running broadcast (IVR retry loop) should run as a background task / worker, not block the request.
- Suggested verify: `uvicorn app.main:app --reload`, `pytest`, and exercise the two client flows against the live OpenAPI docs (`/docs`).
