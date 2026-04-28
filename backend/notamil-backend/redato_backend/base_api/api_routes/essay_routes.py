import asyncio
import base64
import binascii
from typing import Any, Dict, Optional

from redato_backend.base_api.api_routes.models import UploadEssay, UserRole
from redato_backend.base_api.functions.handle_bq import (
    insert_essay_into_bq,
    get_ocr_from_bq,
    get_themes_from_bq,
)
from redato_backend.base_api.functions.professor_feedback import (
    get_professor_feedback,
    upsert_professor_feedback,
)
from redato_backend.base_api.caller import call_cloud_function
from fastapi import APIRouter, Depends, HTTPException, Form
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, Field
from uuid import uuid4

from redato_backend.shared.constants import (
    ESSAYS_ANALYZER_CLOUD_FUNCTION,
    REDATO_API_URL,
    ESSAY_OCR_CLOUD_FUNCTION,
)
from redato_backend.shared.firebase import FirebaseService
from redato_backend.shared.job_tracker import (
    EssayJobTracker,
    JobFunctionType,
    JobStatus,
)
from redato_backend.shared.utils import (
    generate_essay_hash,
    get_analysis_from_bq,
    get_essay_from_bq,
    get_graded_essay_by_hash,
)
from redato_backend.shared.logger import logger


router = APIRouter(prefix="/essays", tags=["essays"])

firebase_service = FirebaseService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

PROFESSOR_ROLES = {
    UserRole.PROFESSOR.value,
    UserRole.SCHOOL_ADMIN.value,
    UserRole.SYSTEM_ADMIN.value,
}

MAX_FEEDBACK_LENGTH = 5000

# OCR upload constraints
MAX_OCR_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB decoded image
_IMAGE_MAGIC_BYTES = (
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"RIFF", "webp"),  # WEBP starts with RIFF; full check below
)


def _truncate(text: Optional[str], limit: int = 500) -> Optional[str]:
    if text is None:
        return None
    return text if len(text) <= limit else text[:limit] + "..."


def _validate_image_payload(base64_file: str) -> None:
    """Validate a base64-encoded image upload.

    Raises HTTPException 400 if the payload is not valid base64, exceeds the
    size limit, or does not look like a supported image format.
    """
    payload = base64_file.strip()
    if payload.startswith("data:"):
        _, _, payload = payload.partition(",")

    try:
        decoded = base64.b64decode(payload, validate=True)
    except (binascii.Error, ValueError):
        raise HTTPException(
            status_code=400, detail="Arquivo de imagem inválido (base64 malformado)."
        )

    if len(decoded) == 0:
        raise HTTPException(status_code=400, detail="Arquivo de imagem vazio.")

    if len(decoded) > MAX_OCR_IMAGE_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Imagem excede o limite de {MAX_OCR_IMAGE_BYTES // (1024 * 1024)} MB.",
        )

    head = decoded[:16]
    detected = None
    for magic, label in _IMAGE_MAGIC_BYTES:
        if head.startswith(magic):
            # For WEBP, also require the WEBP marker at bytes 8..12.
            if label == "webp" and decoded[8:12] != b"WEBP":
                continue
            detected = label
            break

    if detected is None:
        raise HTTPException(
            status_code=400,
            detail="Formato de imagem não suportado. Use JPEG, PNG ou WEBP.",
        )


@router.post("/submit")
async def submit_essay(essay: UploadEssay):
    logger.info(f"Received essay submission from user: {essay.user_id}")
    if not essay.content or not essay.user_id:
        raise HTTPException(
            status_code=400, detail="Content and user_id are required."
        )

    content_hash = generate_essay_hash(essay.content)

    # 1. Check BQ for an already-graded essay with this hash (stable dedup
    #    across sessions, as long as the original grading succeeded).
    existing_analysis_id = get_graded_essay_by_hash(essay.content)
    if existing_analysis_id:
        logger.info(f"Found existing analysis id: {existing_analysis_id}")
        return {
            "message": "Essay already analyzed",
            "request_id": existing_analysis_id,
            "status": JobStatus.COMPLETED.value,
        }

    tracker = EssayJobTracker()

    # 2. Reserve the hash atomically so two concurrent identical submissions
    #    don't both go through grading. First writer wins; the loser gets the
    #    winner's request_id back.
    essay_id = str(uuid4())
    duplicate_id = tracker.reserve_content_hash(content_hash, essay_id)
    if duplicate_id:
        logger.info(
            f"Concurrent duplicate detected for hash {content_hash}; returning {duplicate_id}"
        )
        return {
            "message": "Essay already being analyzed",
            "request_id": duplicate_id,
            "status": JobStatus.PROCESSING.value,
        }

    try:
        essay_id = insert_essay_into_bq(essay, essay_id=essay_id)
    except Exception:
        tracker.release_content_hash(content_hash)
        raise

    tracker.create(
        request_id=essay_id,
        user_id=essay.user_id,
        function_type=JobFunctionType.ESSAY,
        status=JobStatus.PROCESSING,
    )

    # Kick off grading in the background so the client gets control back
    # immediately and can poll /essays/result. This replaces the previous
    # ~45s blocking submit with a fast ACK + polling UX.
    asyncio.create_task(
        _grade_essay_in_background(
            essay_id=essay_id,
            user_id=essay.user_id,
            content=essay.content,
            theme=essay.theme,
            content_hash=content_hash,
        )
    )

    return {
        "message": "Essay submission accepted — grading in progress.",
        "request_id": essay_id,
        "status": JobStatus.PROCESSING.value,
    }


async def _grade_essay_in_background(
    *,
    essay_id: str,
    user_id: str,
    content: str,
    theme: Optional[str],
    content_hash: str,
) -> None:
    """Run the essay grading call off the request path and update job state."""
    tracker = EssayJobTracker()
    try:
        resp = await call_cloud_function(
            ESSAYS_ANALYZER_CLOUD_FUNCTION,
            {
                "user_id": user_id,
                "content": content,
                "theme": theme,
                "request_id": essay_id,
                "callback_url": f"{REDATO_API_URL}/essays/callback/{essay_id}",
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Background grading failed for {essay_id}: {e}")
        tracker.update_status(
            essay_id, JobStatus.FAILED, error_message=_truncate(str(e))
        )
        tracker.release_content_hash(content_hash)
        return

    if resp["status_code"] != 200:
        error_detail = _truncate(resp.get("text") or "Unknown error")
        logger.error(
            f"Essay Cloud Function returned {resp['status_code']} for {essay_id}: {error_detail}"  # noqa: E501
        )
        tracker.update_status(
            essay_id, JobStatus.FAILED, error_message=error_detail
        )
        tracker.release_content_hash(content_hash)
        return

    tracker.update_status(essay_id, JobStatus.COMPLETED)


@router.post("/ocr")
async def process_essay_image(
    user_id: str = Form(...),
    base64_file: str = Form(...),
):
    logger.info(f"Received OCR request for user: {user_id}")

    _validate_image_payload(base64_file)

    ocr_id = str(uuid4())

    tracker = EssayJobTracker()
    tracker.create(
        request_id=ocr_id,
        user_id=user_id,
        function_type=JobFunctionType.OCR,
        status=JobStatus.PROCESSING,
    )

    asyncio.create_task(
        _run_ocr_in_background(
            ocr_id=ocr_id,
            user_id=user_id,
            base64_file=base64_file,
        )
    )

    return {
        "message": "Essay image processing started.",
        "request_id": ocr_id,
        "status": JobStatus.PROCESSING.value,
    }


async def _run_ocr_in_background(
    *, ocr_id: str, user_id: str, base64_file: str
) -> None:
    tracker = EssayJobTracker()
    try:
        resp = await call_cloud_function(
            ESSAY_OCR_CLOUD_FUNCTION,
            {
                "user_id": user_id,
                "request_id": ocr_id,
                "image": base64_file,
                "callback_url": f"{REDATO_API_URL}/essays/callback/{ocr_id}",
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"Background OCR failed for {ocr_id}: {e}")
        tracker.update_status(
            ocr_id, JobStatus.FAILED, error_message=_truncate(str(e))
        )
        return

    if resp["status_code"] != 200:
        error_detail = _truncate(resp.get("text") or "Unknown error")
        tracker.update_status(ocr_id, JobStatus.FAILED, error_message=error_detail)
        return

    tracker.update_status(ocr_id, JobStatus.COMPLETED)


class CallbackPayload(BaseModel):
    status: str
    error_message: Optional[str] = None


@router.post("/callback/{request_id}")
async def essay_callback(request_id: str, payload: CallbackPayload):
    """Idempotent endpoint for Cloud Functions to report final job status.

    Accepts a status string that must be one of JobStatus values and persists
    it to the job tracker. Returns 202 to signal the update was recorded.
    """
    try:
        status = JobStatus(payload.status)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status '{payload.status}'. Expected one of: "
            + ", ".join(s.value for s in JobStatus),
        )

    tracker = EssayJobTracker()
    if tracker.get(request_id) is None:
        logger.warning(
            f"Callback received for unknown request_id={request_id}; creating job entry."
        )

    tracker.update_status(
        request_id, status, error_message=_truncate(payload.error_message)
    )
    return JSONResponse(
        status_code=202,
        content={"request_id": request_id, "status": status.value},
    )


@router.get("/result/{function_type}/{request_id}")
async def get_result(function_type: str, request_id: str):
    """Return structured status + data for a processing request.

    Response shape:
        {
            "request_id": str,
            "status": "pending" | "processing" | "completed" | "failed" | "not_found",
            "data": Optional[dict],
            "error": Optional[str],
        }

    HTTP codes:
        - 200 when completed and data is available
        - 202 when still pending/processing
        - 404 when no job and no data found
        - 422 when job failed
    """
    if function_type not in {"essay", "ocr"}:
        raise HTTPException(
            status_code=400,
            detail="function_type must be 'essay' or 'ocr'.",
        )

    tracker = EssayJobTracker()
    job = tracker.get(request_id)
    job_status = job.get("status") if job else None

    try:
        if function_type == "essay":
            result_data = get_analysis_from_bq(request_id)
            is_complete = bool(
                result_data and result_data.get("competencies")
            )
        else:
            result_data = get_ocr_from_bq(request_id)
            is_complete = bool(
                result_data and result_data.get("content")
            )
    except Exception as e:
        logger.error(
            f"Error retrieving {function_type} data for {request_id}: {e}"
        )
        raise HTTPException(
            status_code=500, detail="Failed to retrieve result data."
        )

    if is_complete:
        raw_audit = job.get("raw_audit") if job else None
        return JSONResponse(
            status_code=200,
            content={
                "request_id": request_id,
                "status": JobStatus.COMPLETED.value,
                "data": result_data,
                "error": None,
                "raw_audit": raw_audit,
            },
        )

    if job_status == JobStatus.FAILED.value:
        return JSONResponse(
            status_code=422,
            content={
                "request_id": request_id,
                "status": JobStatus.FAILED.value,
                "data": None,
                "error": job.get("error_message") or "Processing failed.",
            },
        )

    if job_status in {JobStatus.PENDING.value, JobStatus.PROCESSING.value}:
        preview = job.get("preview_feedback") if job else None
        return JSONResponse(
            status_code=202,
            content={
                "request_id": request_id,
                "status": job_status,
                "data": None,
                "error": None,
                "preview_feedback": preview or None,
            },
        )

    return JSONResponse(
        status_code=404,
        content={
            "request_id": request_id,
            "status": "not_found",
            "data": None,
            "error": "No job or result found for this request_id.",
        },
    )


@router.get("/content/{essay_id}")
async def get_essay(essay_id: str) -> Dict[str, Any]:
    try:
        if not essay_id:
            raise HTTPException(status_code=404, detail="Essay ID is required")

        essay_data = get_essay_from_bq(essay_id)
        if not essay_data:
            raise HTTPException(status_code=404, detail="Essay not found")

        return {
            "essay_id": essay_id,
            "created_at": essay_data.get("created_at", ""),
            "content": essay_data.get("content", ""),
            "original_ocr_content": essay_data.get("original_ocr_content"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting essay from bq: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/themes")
async def get_themes(class_id: str) -> Dict[str, Any]:
    try:
        themes = get_themes_from_bq(class_id)
        return JSONResponse({"data": themes})
    except Exception as e:
        logger.error(f"Error getting themes from bq: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class ProfessorFeedbackPayload(BaseModel):
    feedback_text: str = Field(..., min_length=1, max_length=MAX_FEEDBACK_LENGTH)


@router.get("/{essay_id}/professor-feedback")
async def fetch_professor_feedback(essay_id: str) -> Dict[str, Any]:
    """Return the professor's feedback for an essay (or null if none exists).

    Public to any caller — students see feedback on their own essays; the
    scoping to the correct student is handled at the UI level by only fetching
    essays the student owns.
    """
    try:
        feedback = get_professor_feedback(essay_id)
        return {"data": feedback}
    except Exception as e:
        logger.error(f"Error fetching professor feedback for {essay_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to fetch professor feedback."
        )


@router.post("/{essay_id}/professor-feedback")
async def save_professor_feedback(
    essay_id: str,
    payload: ProfessorFeedbackPayload,
    token: str = Depends(oauth2_scheme),
) -> Dict[str, Any]:
    """Create or update the professor's feedback for an essay.

    Requires a valid Firebase token with a role claim of professor,
    school_admin or system_admin.
    """
    decoded_token = firebase_service.verify_token(token)
    user_role = (decoded_token.get("role") or "").lower()
    professor_id = decoded_token.get("uid")

    if not professor_id:
        raise HTTPException(
            status_code=401, detail="Token is missing a user identifier."
        )

    if user_role not in PROFESSOR_ROLES:
        raise HTTPException(
            status_code=403,
            detail="Only professors and admins can save feedback.",
        )

    feedback_text = payload.feedback_text.strip()
    if not feedback_text:
        raise HTTPException(
            status_code=400, detail="Feedback cannot be empty."
        )

    try:
        upsert_professor_feedback(essay_id, professor_id, feedback_text)
    except Exception as e:
        logger.error(f"Error saving professor feedback for {essay_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to save professor feedback."
        )

    return {
        "message": "Feedback saved successfully.",
        "essay_id": essay_id,
        "professor_id": professor_id,
    }
