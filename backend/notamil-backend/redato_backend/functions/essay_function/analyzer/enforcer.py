from typing import Any, Dict

from redato_backend.functions.essay_function.analyzer.llm_agent import LLMAgent
from redato_backend.functions.essay_function.analyzer.system_prompts import (
    SYSTEM_FEEDBACK_PROMPT,
)
from redato_backend.functions.essay_function.analyzer.prompts import (
    PROMPT_FEEDBACK_GENERATOR,
)


class Enforcer:
    @staticmethod
    def is_essay_valid(essay: str, theme: str) -> bool:
        return len(essay) >= 100 and len(theme) >= 5


class FeedbackGenerator:
    def __init__(self) -> None:
        self.llm = LLMAgent(SYSTEM_FEEDBACK_PROMPT)

    def generate_feedback(
        self, detailed_analysis: Dict[str, Any], grades: Dict[str, Any], essay: str
    ) -> str:
        response = self.llm.generate_response(
            PROMPT_FEEDBACK_GENERATOR.format(
                detailed_analysis=detailed_analysis,
                grades=grades,
                essay=essay,
            )
        )

        return response.get("feedback", "")
