"""Plate verification service layer implementing plate matching business rules."""

import logging
import re
from fastapi import UploadFile, HTTPException, status

from app.vision.interface import VisionProvider
from app.vision.plate_models import PlateVerificationResult

logger = logging.getLogger("uvicorn.error")

SUPPORTED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


def normalize_plate(plate: str) -> str:
    """Normalizes a license plate string by converting to uppercase and stripping non-alphanumeric chars."""
    if not plate:
        return ""
    return re.sub(r'[^A-Z0-9]', '', plate.upper())


class PlateVerificationService:
    """Orchestrates license plate verification, handling both image extraction and manual matching."""

    def __init__(self, provider: VisionProvider):
        self.provider = provider

    async def verify_from_image(
        self, 
        plate_image: UploadFile, 
        registered_plate: str
    ) -> PlateVerificationResult:
        """Extracts the plate from the uploaded image and verifies it against the registered plate."""
        # 1. Validate registered plate input
        if not registered_plate or not registered_plate.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registered plate string cannot be empty.",
            )

        # 2. Validate MIME type
        content_type = plate_image.content_type
        if not content_type or content_type not in SUPPORTED_MIME_TYPES:
            # Fallback check on file extension if content_type is missing/incorrect
            filename_lower = plate_image.filename.lower() if plate_image.filename else ""
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
            image_bytes = await plate_image.read()
        except Exception as e:
            logger.error(f"Failed to read plate image file {plate_image.filename}: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to read plate image file: {plate_image.filename}",
            )
        finally:
            # Reset file position
            await plate_image.seek(0)

        # 3. Call AI provider for plate extraction
        try:
            raw_extraction = await self.provider.extract_plate(image_bytes, content_type)
        except ValueError as val_err:
            logger.warning(f"Validation error in vision provider during plate extraction: {val_err}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(val_err)
            )
        except Exception as provider_err:
            logger.error(f"Failed to extract license plate: {provider_err}")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="AI Vision verification service failed to extract license plate."
            )

        # 4. Process extraction results and compare
        plate_extracted_raw = raw_extraction.get("plate_number")
        confidence = float(raw_extraction.get("confidence", 0.0))
        plate_visible = bool(raw_extraction.get("plate_visible", False))

        norm_registered = normalize_plate(registered_plate)

        if not plate_visible or not plate_extracted_raw:
            return PlateVerificationResult(
                plate_match=False,
                plate_extracted=None,
                plate_registered=norm_registered,
                plate_visible=False,
                confidence=confidence,
                fallback_used=False,
                mismatch_reason="No license plate could be detected or read in the uploaded image."
            )

        norm_extracted = normalize_plate(plate_extracted_raw)
        plate_match = (norm_extracted == norm_registered)

        mismatch_reason = None
        if not plate_match:
            mismatch_reason = f"Extracted plate '{norm_extracted}' does not match registered plate '{norm_registered}'."

        return PlateVerificationResult(
            plate_match=plate_match,
            plate_extracted=norm_extracted,
            plate_registered=norm_registered,
            plate_visible=True,
            confidence=confidence,
            fallback_used=False,
            mismatch_reason=mismatch_reason
        )

    def verify_manual(
        self, 
        manual_plate: str, 
        registered_plate: str
    ) -> PlateVerificationResult:
        """Directly compares manual entry against registered plate with normalization."""
        if not manual_plate or not manual_plate.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Manual plate string cannot be empty.",
            )

        if not registered_plate or not registered_plate.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Registered plate string cannot be empty.",
            )

        norm_manual = normalize_plate(manual_plate)
        norm_registered = normalize_plate(registered_plate)

        plate_match = (norm_manual == norm_registered)

        mismatch_reason = None
        if not plate_match:
            mismatch_reason = f"Manual entry '{norm_manual}' does not match registered plate '{norm_registered}'."

        return PlateVerificationResult(
            plate_match=plate_match,
            plate_extracted=norm_manual,
            plate_registered=norm_registered,
            plate_visible=False,
            confidence=1.0,
            fallback_used=True,
            mismatch_reason=mismatch_reason
        )
