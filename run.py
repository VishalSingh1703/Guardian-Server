"""Local development entrypoint.

Run with ``python run.py`` (or use ``uvicorn app.main:app --reload`` directly).
"""

import os
import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    # Uvicorn auto-reload is known to hang on Windows with background asyncio/websockets.
    # We disable it by default on Windows (os.name == 'nt'), but keep it enabled by default elsewhere.
    reload_default = "false" if os.name == "nt" else "true"
    reload_flag = os.getenv("RELOAD", reload_default).lower() == "true"
    
    print(f"Starting Uvicorn server on {settings.HOST}:{settings.PORT} (reload={reload_flag})...")
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=reload_flag)
