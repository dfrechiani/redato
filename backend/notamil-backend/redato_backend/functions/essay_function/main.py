from typing import Any, Dict, Tuple

import functions_framework

from redato_backend.functions.essay_function.analyzer.essay_analyzer import EssayAnalyzer
from redato_backend.functions.essay_function.utils import validate_and_callback
from redato_backend.functions.essay_function.models import (
    EssayProcessingError,
    EssayRequestModel,
)
from redato_backend.functions.essay_function.analyzer.enforcer import FeedbackGenerator
from redato_backend.functions.essay_function.utils import insert_essay_graded_into_bq
from redato_backend.shared.logger import logger
from redato_backend.shared.utils import generate_essay_hash


@functions_framework.http
def essay_handler(request) -> Tuple[Dict[str, Any], int]:  # noqa: C901
    try:
        request_json = request.get_json()
        if not request_json:
            raise EssayProcessingError("No request data received")

        data = EssayRequestModel(**request_json)
        if not data.callback_url:
            return {"error": "No callback URL provided"}, 400
    except Exception as e:
        logger.error(f"Request validation failed: {str(e)}")
        return {"error": "Invalid request format", "details": str(e)}, 400

    if not validate_and_callback(data):
        return {"error": "Essay not in a valid format"}, 400

    try:
        if not data.content:
            return {"error": "No content provided"}, 400

        essay_analyzer = EssayAnalyzer()
        essay_graded = essay_analyzer.process_complete_essay(data.content, data.theme)
        feedback_generator = FeedbackGenerator()
        feedback = feedback_generator.generate_feedback(
            essay_graded.detailed_analysis, essay_graded.grades, data.content
        )

        essay_hash = generate_essay_hash(data.content)

        insert_essay_graded_into_bq(
            data.request_id, essay_graded, data.user_id, feedback, essay_hash
        )

        return {"message": "Analysis completed and published"}, 200
    except Exception as e:
        logger.error(f"Error during essay analysis for user {data.user_id}: {str(e)}")
        return {"error": str(e)}, 500
