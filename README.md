# Guardian-Server

Backend & integration hub for the **Guardian** platform. See [`CLAUDE.md`](./CLAUDE.md) for full component context and the platform PRD (`root.md` in the workspace root) for product scope.

## Project structure

```
run.py                 # local dev entrypoint
app/
  main.py              # create_app() — builds the FastAPI app, registers routers
  core/config.py       # Settings — single source of truth for environment config
  schemas/             # Pydantic request/response models
  routers/             # HTTP layer (health, telephony) — thin, delegates to services
  services/            # business logic (telephony call flow; Twilio integration)
```

Layered architecture: `routers` (transport) → `services` (business logic) → `core/config` (env). Add a feature by adding a router + service and registering the router in `app/main.py`.

## Getting started

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # then fill in real values
python run.py               # or: uvicorn app.main:app --reload
```

Server runs on `http://localhost:8000` (configurable via `HOST`/`PORT`). Interactive API docs at `/docs`.

## Endpoints (current)

| Method | Path    | Purpose                                            |
|--------|---------|----------------------------------------------------|
| `GET`  | `/`     | Health check + config status.                      |
| `POST` | `/call` | Trigger an outbound call (currently a simulation). |
