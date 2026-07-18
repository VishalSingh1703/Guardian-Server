"""Abstract interface for vision providers.

Allows modular, swappable AI vision backends (e.g. Gemini, Anthropic/Claude).
"""

from abc import ABC, abstractmethod
from typing import Dict, Any

from app.vision.models import DamageAnalysisResult


class VisionProvider(ABC):
    """Abstract base class defining the interface for all vision providers."""

    @abstractmethod
    async def analyze_damage(
        self, 
        images: list[bytes], 
        mime_types: list[str]
    ) -> Dict[str, Any]:
        """Analyzes multiple image bytes for structural vehicle damage.

        Args:
            images: List of image files as bytes.
            mime_types: Corresponding list of MIME types (e.g. image/jpeg).

        Returns:
            A dictionary containing the parsed model response matching key fields:
            - damage_confirmed: bool
            - confidence: float
            - damage_description: str
            - analysis_notes: str
        """
        pass

    @abstractmethod
    async def extract_plate(
        self,
        image: bytes,
        mime_type: str
    ) -> Dict[str, Any]:
        """Extracts the license plate number from a single image.

        Args:
            image: Image file as bytes.
            mime_type: MIME type of the image (e.g. image/jpeg).

        Returns:
            A dictionary containing the parsed model response matching key fields:
            - plate_number: str | None
            - confidence: float
            - plate_visible: bool
        """
        pass
