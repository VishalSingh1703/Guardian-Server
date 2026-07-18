"""Pydantic schemas for the vision verification module.

Defines the response contract for image verification requests.
"""

from pydantic import BaseModel, Field


class DamageAnalysisResult(BaseModel):
    """Result of the vehicle damage verification analysis."""

    verified: bool = Field(
        ...,
        description="Whether structural damage is verified above the required confidence threshold.",
    )
    confidence: float = Field(
        ...,
        description="Confidence score of the AI analysis (between 0.0 and 1.0).",
    )
    damage_confirmed: bool = Field(
        ...,
        description="True if structural vehicle damage was identified in the images.",
    )
    damage_description: str = Field(
        ...,
        description="Detailed description of the observed structural damage.",
    )
    analysis_notes: str = Field(
        ...,
        description="Forensic analysis notes detailing features or objects identified in the frames.",
    )
    image_count_analyzed: int = Field(
        ...,
        description="The number of image frames analyzed in this request.",
    )
    threshold_used: float = Field(
        ...,
        description="The confidence threshold value used for verification.",
    )
