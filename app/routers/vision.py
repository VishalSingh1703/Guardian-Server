"""Vision routes for processing image verification requests."""

from fastapi import APIRouter, File, UploadFile, HTTPException, status, Depends, Form

from app.vision.models import DamageAnalysisResult
from app.vision.plate_models import PlateVerificationResult, ManualPlateVerifyRequest, UnifiedVerificationResult
from app.vision.providers.gemini import GeminiVisionProvider
from app.vision.service import VisionService
from app.vision.plate_service import PlateVerificationService

router = APIRouter(prefix="/vision", tags=["vision"])


def get_vision_service() -> VisionService:
    """Dependency provider that instantiates the VisionService with the default Gemini provider."""
    try:
        provider = GeminiVisionProvider()
        return VisionService(provider)
    except ValueError as val_err:
        # Raise 503 if API key / settings are missing or incomplete
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Vision verification service is currently unconfigured: {str(val_err)}"
        )


def get_plate_service() -> PlateVerificationService:
    """Dependency provider that instantiates the PlateVerificationService with the default Gemini provider."""
    try:
        provider = GeminiVisionProvider()
        return PlateVerificationService(provider)
    except ValueError as val_err:
        # Raise 503 if API key / settings are missing or incomplete
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Plate verification service is currently unconfigured: {str(val_err)}"
        )


@router.post(
    "/webapp/analyze", 
    response_model=DamageAnalysisResult, 
    status_code=status.HTTP_200_OK,
    summary="Verify structural vehicle damage from Webapp uploads"
)
async def analyze_webapp_images(
    images: list[UploadFile] = File(..., description="1 to 5 image frames photographed by a bystander"),
    service: VisionService = Depends(get_vision_service)
):
    """
    Takes 1 to 5 images uploaded from the Guardian Webapp, passes them to the AI Vision model,
    and returns whether structural damage is verified based on the AI's confidence score.
    """
    return await service.analyze_webapp_images(images)


@router.post(
    "/plate/verify",
    response_model=PlateVerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Extract plate from photo and verify against registered plate"
)
async def verify_plate_image(
    plate_image: UploadFile = File(..., description="Photo containing the vehicle license plate"),
    registered_plate: str = Form(..., description="Registered license plate number to match against"),
    service: PlateVerificationService = Depends(get_plate_service)
):
    """
    Takes a single vehicle plate image, extracts the plate number via Gemini, and compares
    it with the expected registered plate. Normalizes format discrepancies.
    """
    return await service.verify_from_image(plate_image, registered_plate)


@router.post(
    "/plate/verify-manual",
    response_model=PlateVerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Manually verify license plate input against registered plate"
)
def verify_plate_manual(
    payload: ManualPlateVerifyRequest,
    service: PlateVerificationService = Depends(get_plate_service)
):
    """
    Manually checks user typed plate input against the expected registered plate.
    Performs the same normalization logic as the image endpoint. No AI involved.
    """
    return service.verify_manual(payload.manual_plate, payload.registered_plate)


@router.post(
    "/verify-incident",
    response_model=UnifiedVerificationResult,
    status_code=status.HTTP_200_OK,
    summary="Verify vehicle plate and damage sequentially in a single request"
)
async def verify_incident(
    registered_plate: str = Form(..., description="Expected plate from QR scan"),
    damage_images: list[UploadFile] = File(..., description="1 to 5 photos of vehicle damage"),
    plate_image: UploadFile | None = File(None, description="Optional plate photo for OCR"),
    manual_plate: str | None = Form(None, description="Optional manual plate text fallback"),
    vision_service: VisionService = Depends(get_vision_service),
    plate_service: PlateVerificationService = Depends(get_plate_service)
):
    """
    Orchestrates sequential verification of the incident:
    1. Plate matching (checks plate_image or falls back to manual_plate).
    2. Short-circuits damage analysis if plate verification fails.
    3. Runs damage analysis if plate matches.
    """
    # 1. Perform plate verification
    if plate_image is not None and plate_image.filename:
        plate_result = await plate_service.verify_from_image(plate_image, registered_plate)
    elif manual_plate is not None and manual_plate.strip():
        plate_result = plate_service.verify_manual(manual_plate, registered_plate)
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either a plate_image file or a manual_plate string must be provided for verification."
        )

    # 2. Check match. If mismatch, short-circuit and return immediately
    if not plate_result.plate_match:
        return UnifiedVerificationResult(
            overall_verified=False,
            plate_result=plate_result,
            damage_result=None
        )

    # 3. Plate matches, proceed to damage verification
    damage_result = await vision_service.analyze_webapp_images(damage_images)
    overall_verified = damage_result.verified

    return UnifiedVerificationResult(
        overall_verified=overall_verified,
        plate_result=plate_result,
        damage_result=damage_result
    )
