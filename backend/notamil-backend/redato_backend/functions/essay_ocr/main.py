from typing import Any, Dict, Tuple

import functions_framework

from redato_backend.functions.essay_ocr.utils import insert_ocr_into_bq
from redato_backend.functions.essay_ocr.vision.anthropic_vision import (
    AnthropicVisionAgent,
)
from redato_backend.functions.essay_ocr.vision.models import (
    ImageDecodingError,
    JSONProcessingError,
    OCRProcessingError,
    VisionProcessingError,
    VisionRequest,
)
from redato_backend.shared.logger import logger


@functions_framework.http
def ocr_handler(request) -> Tuple[Dict[str, Any], int]:  # noqa: C901
    try:
        request_json = request.get_json()
        if not request_json:
            raise OCRProcessingError("No request data received")

        data = VisionRequest(**request_json)
    except Exception as e:
        logger.error(f"Request validation failed: {str(e)}")
        return {"error": "Invalid request format", "details": str(e)}, 400

    try:
        logger.info(f"Received OCR request from user_id: {data.user_id}")

        if not data.image:
            logger.error(f"No image received for user_id: {data.user_id}")
            return {"error": "No image received"}, 422

        vision_model = AnthropicVisionAgent(data.image)
        ocr_transcription, ocr_accuracy = vision_model.deploy()

        insert_ocr_into_bq(
            ocr_transcription, data.user_id, data.request_id, ocr_accuracy.accuracy
        )

        logger.info(f"Successfully processed image for user_id: {data.user_id}")
        return {"message": "OCR completed successfully"}, 200

    except (
        OCRProcessingError,
        ImageDecodingError,
        JSONProcessingError,
        VisionProcessingError,
    ) as e:
        logger.error(f"{e.__class__.__name__} for user_id {data.user_id}: {str(e)}")
        return {"error": e.__class__.__name__, "details": str(e)}, 422

    except Exception as e:
        logger.critical(f"Unexpected error in vision handler: {str(e)}", exc_info=True)
        return {
            "error": "Internal server error",
            "request_id": request.headers.get("X-Request-ID", "unknown"),
        }, 500
