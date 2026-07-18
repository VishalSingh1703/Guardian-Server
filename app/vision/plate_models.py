"""Pydantic schemas for license plate verification."""

from pydantic import BaseModel, Field


class PlateVerificationResult(BaseModel):
    """Result of license plate verification (both image-based and manual)."""

    plate_match: bool = Field(
        ...,
        description="True if the extracted or manual plate matches the registered plate (ignoring format differences)."
    )
    plate_extracted: str | None = Field(
        ...,
        description="The normalized license plate string extracted from the image or manually entered by the user."
    )
    plate_registered: str = Field(
        ...,
        description="The normalized registered plate string that was compared against."
    )
    plate_visible: bool = Field(
        ...,
        description="True if a plate was successfully located and read in the image (always False for manual entries)."
    )
    confidence: float = Field(
        ...,
        description="The confidence score of plate extraction (from 0.0 to 1.0; 1.0 if manual fallback was used)."
    )
    fallback_used: bool = Field(
        ...,
        description="True if the validation was done via manual text input fallback instead of image analysis."
    )
    mismatch_reason: str | None = Field(
        None,
        description="A human-readable reason detailing why verification failed, if applicable."
    )


class ManualPlateVerifyRequest(BaseModel):
    """Input payload schema for the manual fallback plate verification endpoint."""

    manual_plate: str = Field(
        ...,
        min_length=1,
        description="The raw license plate string entered manually by the user."
    )
    registered_plate: str = Field(
        ...,
        min_length=1,
        description="The raw registered license plate string to verify against."
    )


class UnifiedVerificationResult(BaseModel):
    """Combined results of plate matching and damage analysis."""

    overall_verified: bool = Field(
        ...,
        description="True only if both plate verification and damage verification succeeded."
    )
    plate_result: PlateVerificationResult = Field(
        ...,
        description="Detailed result of the license plate verification gate."
    )
    damage_result: "DamageAnalysisResult | None" = Field(
        None,
        description="Detailed result of the damage analysis gate. Null if plate matching failed."
    )


# Avoid circular imports since DamageAnalysisResult imports from standard models
from app.vision.models import DamageAnalysisResult
UnifiedVerificationResult.model_rebuild()
