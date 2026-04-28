from typing import Any, Dict, List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query

from redato_backend.base_api.api_routes.deps import require_auth
from redato_backend.base_api.caller import call_cloud_function
from redato_backend.base_api.functions.models import UserRole
from redato_backend.shared.constants import TUTOR_CLOUD_FUNCTION
from redato_backend.shared.firestore import FirestoreCache
from redato_backend.shared.logger import logger
from redato_backend.shared.models import TutorRequest


router = APIRouter(prefix="/intelligence", tags=["intelligence"])


_STAFF_ROLES = {
    UserRole.PROFESSOR.value.lower(),
    UserRole.SCHOOL_ADMIN.value.lower(),
    UserRole.SYSTEM_ADMIN.value.lower(),
}


@router.post("/tutor")
async def chat_tutor(
    conversation: TutorRequest,
    user: Dict[str, Any] = Depends(require_auth),
) -> Tuple[Dict[str, Any], int]:
    token_uid = user.get("uid")
    token_role = (user.get("role") or "").lower()

    # Students can only query the tutor about their own essays. Professors and
    # admins may query on behalf of any student so they can inspect the tutor's
    # response while coaching.
    if token_role not in _STAFF_ROLES and conversation.user_id != token_uid:
        logger.warning(
            f"Forbidden: uid={token_uid} attempted to query tutor as user_id={conversation.user_id}"  # noqa: E501
        )
        raise HTTPException(
            status_code=403,
            detail="You cannot query the tutor on behalf of another user.",
        )

    try:
        logger.info(f"Tutor called by: {conversation.user_id}")

        request_data = conversation.model_dump()
        tutor_response = await call_cloud_function(TUTOR_CLOUD_FUNCTION, request_data)

        if not tutor_response:
            raise HTTPException(
                status_code=500, detail="No response received from cloud function"
            )

        response_json = tutor_response.get("json")
        status_code = tutor_response.get("status_code", 500)

        if not response_json:
            raise HTTPException(
                status_code=status_code,
                detail="Invalid response format from cloud function",
            )

        return response_json, status_code

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tutor failed with error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@router.get("/tutor/history")
def get_tutor_history(
    essay_id: str = Query(..., description="Essay the conversation is attached to"),
    user_id: str = Query(..., description="Student user id"),
    user: Dict[str, Any] = Depends(require_auth),
) -> Dict[str, List[Dict[str, Any]]]:
    """Return the stored tutor conversation for (user_id, essay_id).

    Students can only fetch their own history; professors/admins may fetch any.
    """
    token_uid = user.get("uid")
    token_role = (user.get("role") or "").lower()

    if token_role not in _STAFF_ROLES and user_id != token_uid:
        raise HTTPException(
            status_code=403,
            detail="You cannot read another user's tutor history.",
        )

    try:
        cache = FirestoreCache()
        conversation = cache.get_conversation(client_id=user_id, chat_id=essay_id)
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in conversation.conversation
            if isinstance(msg.content, str)
        ]
        return {"messages": messages}
    except Exception as e:
        logger.error(f"Failed to read tutor history for essay {essay_id}: {e}")
        raise HTTPException(
            status_code=500, detail="Failed to read tutor conversation history."
        )
