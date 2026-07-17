"""Vision service layer orchestrating image analysis and applying business rules."""

import logging
from fastapi import UploadFile, HTTPException, status

from app.core.config import settings
from app.vision.interface import VisionProvider
from app.vision.models import DamageAnalysisResult

logger = logging.getLogger("uvicorn.error")

SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MIN_IMAGES = 1
MAX_IMAGES = 5


class VisionService:
    """Orchestrates vision verification flows, validating files and applying confidence thresholds."""

    def __init__(self, provider: VisionProvider):
        self.provider = provider

    async def analyze_webapp_images(self, files: list[UploadFile]) -> DamageAnalysisResult:
        """Validates incoming image files, requests AI inspection, and flags verification.

        Args:
            files: List of FastAPI UploadFile objects.

        Returns:
            A populated DamageAnalysisResult response schema.
        """
        # 1. Validate image list constraints
        if not files or len(files) < MIN_IMAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"At least {MIN_IMAGES} image file is required.",
            )
        
        if len(files) > MAX_IMAGES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum of {MAX_IMAGES} images can be analyzed at once.",
            )

        # 2. Extract bytes and validate MIME types
        image_data_list = []
        mime_types = []

        for file in files:
            content_type = file.content_type
            if not content_type or content_type not in SUPPORTED_MIME_TYPES:
                # Fallback check on file extension if content_type is missing/incorrect
                filename_lower = file.filename.lower() if file.filename else ""
                if filename_lower.endswith((".jpg", ".jpeg")):
                    content_type = "image/jpeg"
                elif filename_lower.endswith(".png"):
                    content_type = "image/png"
                elif filename_lower.endswith(".webp"):
                    content_type = "image/webp"
                else:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Unsupported file type. Supported types: {', '.join(SUPPORTED_MIME_TYPES)}",
                    )
            
            try:
                # Read file bytes
                file_bytes = await file.read()
                image_data_list.append(file_bytes)
                mime_types.append(content_type)
            except Exception as e:
                logger.error(f"Failed to read upload file {file.filename}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read image file: {file.filename}",
                )
            finally:
                # Reset file position just in case
                await file.seek(0)

        # 3. Call AI provider
        try:
            raw_analysis = await self.provider.analyze_damage(image_data_list, mime_types)
        except ValueError as val_err:
            logger.warning(f"Validation error in vision provider: {val_err}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(val_err)
            )
        except Exception as provider_err:
            logger.error(f"Failed to run damage analysis: {provider_err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI Vision verification service failed to complete analysis."
            )

        # 4. Apply safety thresholds and compile final result
        damage_confirmed = raw_analysis.get("damage_confirmed", False)
        confidence = float(raw_analysis.get("confidence", 0.0))
        damage_description = raw_analysis.get("damage_description", "")
        analysis_notes = raw_analysis.get("analysis_notes", "")

        # Verify = damage is confirmed AND confidence meets/exceeds the configured threshold
        threshold = settings.VISION_CONFIDENCE_THRESHOLD
        verified = damage_confirmed and (confidence >= threshold)

        return DamageAnalysisResult(
            verified=verified,
            confidence=confidence,
            damage_confirmed=damage_confirmed,
            damage_description=damage_description,
            analysis_notes=analysis_notes,
            image_count_analyzed=len(files),
            threshold_used=threshold,
        )
