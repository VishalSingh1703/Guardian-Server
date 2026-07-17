"""Vision routes for processing image verification requests."""

from fastapi import APIRouter, File, UploadFile, HTTPException, status, Depends

from app.vision.models import DamageAnalysisResult
from app.vision.providers.gemini import GeminiVisionProvider
from app.vision.service import VisionService

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
