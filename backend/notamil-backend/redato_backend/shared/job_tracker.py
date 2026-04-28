from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Optional

from google.api_core import exceptions as gcp_exceptions
from google.cloud import firestore

from redato_backend.shared.constants import FIRESTORE_DATABASE_NAME
from redato_backend.shared.logger import logger


ESSAY_JOBS_COLLECTION = "essay_jobs"
ESSAY_CONTENT_HASHES_COLLECTION = "essay_content_hashes"


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class JobFunctionType(str, Enum):
    ESSAY = "essay"
    OCR = "ocr"


class EssayJobTracker:
    """Tracks the lifecycle of essay/OCR processing jobs in Firestore.

    Firestore is used instead of BigQuery because BQ streaming inserts go into
    a buffer that blocks DML UPDATE for up to ~90 minutes. Job state must be
    mutable within seconds of creation.
    """

    def __init__(self) -> None:
        try:
            self._db = firestore.Client(database=FIRESTORE_DATABASE_NAME)
            self._collection = self._db.collection(ESSAY_JOBS_COLLECTION)
            self._hashes_collection = self._db.collection(
                ESSAY_CONTENT_HASHES_COLLECTION
            )
        except Exception as e:
            logger.error(f"Failed to connect to Firestore for job tracking: {e}")
            self._db = None
            self._collection = None
            self._hashes_collection = None

    def create(
        self,
        request_id: str,
        user_id: str,
        function_type: JobFunctionType,
        status: JobStatus = JobStatus.PENDING,
    ) -> None:
        if not self._collection:
            return
        try:
            now = datetime.now(timezone.utc)
            self._collection.document(request_id).set(
                {
                    "request_id": request_id,
                    "user_id": user_id,
                    "function_type": function_type.value,
                    "status": status.value,
                    "error_message": None,
                    "created_at": now,
                    "updated_at": now,
                }
            )
            logger.info(
                f"Job created: request_id={request_id} type={function_type.value} status={status.value}"  # noqa: E501
            )
        except Exception as e:
            logger.error(f"Failed to create job {request_id}: {e}")

    def update_status(
        self,
        request_id: str,
        status: JobStatus,
        error_message: Optional[str] = None,
    ) -> None:
        if not self._collection:
            return
        try:
            payload: Dict[str, Any] = {
                "status": status.value,
                "updated_at": datetime.now(timezone.utc),
            }
            if error_message is not None:
                payload["error_message"] = error_message
            self._collection.document(request_id).set(payload, merge=True)
            logger.info(
                f"Job updated: request_id={request_id} status={status.value}"
            )
        except Exception as e:
            logger.error(f"Failed to update job {request_id}: {e}")

    def append_preview(self, request_id: str, chunk: str) -> None:
        """Append a chunk of streamed preview feedback to the job doc.

        Used while the quick-preview call is streaming so the frontend can
        render partial feedback before the full grading finishes.
        """
        if not self._collection:
            return
        try:
            doc_ref = self._collection.document(request_id)
            snapshot = doc_ref.get()
            current = ""
            if snapshot.exists:
                current = (snapshot.to_dict() or {}).get("preview_feedback") or ""
            doc_ref.set(
                {
                    "preview_feedback": current + chunk,
                    "updated_at": datetime.now(timezone.utc),
                },
                merge=True,
            )
        except Exception as e:
            logger.warning(f"Failed to append preview for {request_id}: {e}")

    def get(self, request_id: str) -> Optional[Dict[str, Any]]:
        if not self._collection:
            return None
        try:
            snapshot = self._collection.document(request_id).get()
            if not snapshot.exists:
                return None
            return snapshot.to_dict()
        except Exception as e:
            logger.error(f"Failed to read job {request_id}: {e}")
            return None

    def reserve_content_hash(
        self, content_hash: str, request_id: str
    ) -> Optional[str]:
        """Atomically claim a content hash for the given request_id.

        Uses Firestore's create() which fails if the document already exists —
        so only one concurrent submission of identical content will succeed.

        Returns:
            None if the hash was reserved successfully (caller owns it and
            should proceed with grading).
            The existing request_id string if another submission already
            reserved this hash (caller should return that request_id to the
            user instead of double-grading).
        """
        if not self._hashes_collection:
            return None  # Firestore unavailable — fall through without dedup

        doc_ref = self._hashes_collection.document(content_hash)
        try:
            doc_ref.create(
                {
                    "content_hash": content_hash,
                    "request_id": request_id,
                    "created_at": datetime.now(timezone.utc),
                }
            )
            return None
        except gcp_exceptions.AlreadyExists:
            try:
                existing = doc_ref.get().to_dict() or {}
                return existing.get("request_id")
            except Exception as e:
                logger.error(
                    f"Hash {content_hash} is reserved but could not be read back: {e}"
                )
                return None
        except Exception as e:
            logger.error(f"Failed to reserve content hash {content_hash}: {e}")
            return None

    def release_content_hash(self, content_hash: str) -> None:
        """Delete a hash reservation — call on processing failure so the user
        can retry without hitting a stale duplicate entry.
        """
        if not self._hashes_collection:
            return
        try:
            self._hashes_collection.document(content_hash).delete()
            logger.info(f"Released content hash reservation: {content_hash}")
        except Exception as e:
            logger.warning(
                f"Failed to release content hash {content_hash}: {e}"
            )
