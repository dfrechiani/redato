import json
from typing import Dict, Any

from litellm import completion

from redato_backend.shared.constants import (
    OPENAI_API_KEY,
    OPENAI_GPT_MODEL,
)


class LLMAgent:
    """
    Wrapper simplificado para o cliente GPT usando LiteLLM.
    """

    def __init__(self, system_prompt: str):
        self.system_prompt = system_prompt

    def generate_response(self, prompt: str) -> Dict[str, Any]:
        """
        Gera uma resposta a partir de um prompt usando o modelo GPT via LiteLLM.
        O GPT retornará resultados no formato JSON.
        """
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt},
        ]

        response = completion(
            model=OPENAI_GPT_MODEL,
            messages=messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            api_key=OPENAI_API_KEY,
        )

        content = response.choices[0].message.content
        try:
            return json.loads(content)
        except json.JSONDecodeError as e:
            return {"error": str(e)}
