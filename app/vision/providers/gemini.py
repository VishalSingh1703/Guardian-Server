"""Gemini Vision provider implementation."""

import json
import logging
from typing import Dict, Any
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.core.config import settings
from app.vision.interface import VisionProvider
from app.vision.prompts import DAMAGE_DETECTION_SYSTEM_PROMPT, DAMAGE_DETECTION_USER_PROMPT

logger = logging.getLogger("uvicorn.error")


class GeminiDamageResponse(BaseModel):
    """Pydantic schema used to constrain the Gemini JSON response."""

    damage_confirmed: bool = Field(
        ..., 
        description="True if structural vehicle damage was identified in the images."
    )
    confidence: float = Field(
        ..., 
        description="Confidence score of the AI analysis (between 0.0 and 1.0)."
    )
    damage_description: str = Field(
        ..., 
        description="Detailed description of the observed structural damage."
    )
    analysis_notes: str = Field(
        ..., 
        description="Forensic analysis notes detailing features or objects identified in the frames."
    )


class GeminiVisionProvider(VisionProvider):
    """Gemini-based concrete implementation of VisionProvider."""

    def __init__(self):
        if not settings.gemini_configured:
            raise ValueError("Gemini API key is not configured in settings.")
        
        # Initialize Google GenAI client using the config API key
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL

    async def analyze_damage(
        self, 
        images: list[bytes], 
        mime_types: list[str]
    ) -> Dict[str, Any]:
        """Analyzes multiple image bytes for structural vehicle damage using Gemini Vision."""
        if not images:
            raise ValueError("No images provided for analysis.")

        if len(images) != len(mime_types):
            raise ValueError("The number of images must match the number of mime types.")

        # Prepare content parts (images + prompt text)
        contents = []
        for img_bytes, mime_type in zip(images, mime_types):
            part = types.Part.from_bytes(
                data=img_bytes,
                mime_type=mime_type
            )
            contents.append(part)
        
        # Add the analysis prompt
        contents.append(DAMAGE_DETECTION_USER_PROMPT)

        try:
            logger.info(f"Calling Gemini model {self.model_name} with {len(images)} images...")
            
            # Use the async client (client.aio) to execute non-blocking API calls
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=DAMAGE_DETECTION_SYSTEM_PROMPT,
                    response_mime_type="application/json",
                    response_schema=GeminiDamageResponse,
                )
            )

            result_text = response.text
            if not result_text:
                raise ValueError("Received empty response from Gemini model.")

            logger.info("Successfully received structured response from Gemini Vision.")
            return json.loads(result_text)

        except Exception as e:
            logger.error(f"Error calling Gemini Vision API: {str(e)}")
            raise e
