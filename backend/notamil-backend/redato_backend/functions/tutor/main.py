from typing import Dict, Any, Tuple

import functions_framework

from redato_backend.shared.models import TutorRequest
from redato_backend.functions.tutor.tutor_agent import OpenAIGenerativeAgent
from redato_backend.functions.tutor.prompt import TUTOR_PROMPT
from redato_backend.functions.tutor.utils import get_errors_analysis

from redato_backend.shared.firestore import FirestoreCache
from redato_backend.shared.logger import logger
from redato_backend.shared.utils import get_analysis_from_bq, get_essay_from_bq


def create_user_message(message_body: str) -> Dict[str, Any]:
    """Create a user message dictionary based on message data."""

    return {"role": "user", "content": message_body}


@functions_framework.http
def chat_tutor(request) -> Tuple[Dict[str, Any], int]:
    try:
        request_json = request.get_json()
        tutor_request = TutorRequest(**request_json)

        essay_analysis = get_analysis_from_bq(tutor_request.essay_id)
        essay_content = get_essay_from_bq(tutor_request.essay_id)

        if not essay_analysis or not essay_content:
            logger.error("Failed to get essay for tutor")
            return {"message": "Failed to get essay for tutor", "status": "error"}, 404

        prompt = TUTOR_PROMPT.format(
            errors=tutor_request.errors,
            competency=tutor_request.competency,
            error_analysis=get_errors_analysis(essay_analysis),
            essay_content=essay_content,
        )
        firestore_cache: FirestoreCache = FirestoreCache()
        conversation_model = firestore_cache.get_conversation(
            tutor_request.user_id, tutor_request.essay_id
        )

        conversation_model.append_message(create_user_message(tutor_request.message))

        agent = OpenAIGenerativeAgent(prompt)

        response = agent.generate_response(conversation_model)

        firestore_cache.set_conversation(
            tutor_request.user_id, tutor_request.essay_id, conversation_model
        )

        return {"response": response}, 200

    except Exception as e:
        logger.error(f"Error on tutor talking to OpenAI: {e}")
        raise e
