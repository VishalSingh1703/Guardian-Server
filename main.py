import os
from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from services import initiate_call_flow

app = FastAPI(
    title="Guardian AI Telephony Server",
    description="FastAPI server to orchestrate Twilio calls with Pipecat and Gemini Live",
    version="0.1.0"
)

# Pydantic schemas for request validation
class CallRequest(BaseModel):
    to_phone: str = Field(
        ..., 
        description="The target phone number to call (E.164 format, e.g., +1234567890)",
        examples=["+1987654321"]
    )
    from_phone: str = Field(
        None, 
        description="The source phone number. If not provided, TWILIO_PHONE_NUMBER from environment is used.",
        examples=["+1234567890"]
    )

@app.get("/", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint to ensure server is running.
    """
    return {
        "status": "online",
        "server": "Guardian AI Telephony Temp Server",
        "configs_loaded": {
            "twilio_configured": os.getenv("TWILIO_ACCOUNT_SID") != "your_twilio_account_sid_here",
            "server_url": os.getenv("SERVER_URL")
        }
    }

@app.post("/call", status_code=status.HTTP_200_OK)
async def make_call(payload: CallRequest):
    """
    Triggers an outbound call by invoking the service layer.
    """
    try:
        result = initiate_call_flow(
            to_phone=payload.to_phone,
            from_phone=payload.from_phone
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate call flow: {str(e)}"
        )

if __name__ == "__main__":
    import uvicorn
    # Read port/host from env or use defaults
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("main:app", host=host, port=port, reload=True)
