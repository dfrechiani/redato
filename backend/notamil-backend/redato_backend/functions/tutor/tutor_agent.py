import json

from typing import Any, Dict, List, Union

from openai import OpenAI
from openai.types.chat import ChatCompletion

from redato_backend.functions.tutor.tools import TOOLS_REGISTRY
from redato_backend.shared.constants import OPENAI_API_KEY, OPENAI_GPT_MODEL
from redato_backend.shared.logger import logger
from redato_backend.shared.models import ConversationMessage, FirestoreConversationModel


class OpenAIGenerativeAgent:
    def __init__(self, prompt: str) -> None:
        super().__init__()
        self.openai = OpenAI(api_key=OPENAI_API_KEY)
        self.prompt = prompt

    def _append_system_prompt(
        self, user_messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Initializes a new conversation with the system prompt.
        """
        return [
            {
                "role": "system",
                "content": self.prompt,
            }
        ] + user_messages

    def call_gpt(  # noqa: C901
        self,
        messages: List[Union[Dict[str, Any], ConversationMessage]],
    ) -> Union[ChatCompletion, Dict[str, Any]]:
        """Call GPT with validated message ordering."""
        try:
            messages_dict = [
                msg.model_dump() if hasattr(msg, "model_dump") else msg
                for msg in messages
            ]

            messages_to_gpt = self._append_system_prompt(messages_dict)

            response = self.openai.chat.completions.create(
                model=OPENAI_GPT_MODEL,
                messages=messages_to_gpt,
            )
            return response

        except Exception as e:
            logger.error(f"Error generating AI message: {e}")
            return {"error": str(e)}

    def handle_function_call(  # noqa: C901
        self,
        response_message: Any,
        conversation: FirestoreConversationModel,
    ) -> Union[ChatCompletion, Dict[str, Any]]:
        """Handle function calls and save responses to conversation."""
        try:
            tool_calls = response_message.tool_calls
            if not tool_calls:
                return {"error": "No tool_calls in response_message"}

            # Process all tool calls and save responses
            for tool_call in tool_calls:
                function_name = tool_call.function.name
                arguments = tool_call.function.arguments
                tool_call_id = tool_call.id
                try:

                    try:
                        function_args = json.loads(arguments)
                    except json.JSONDecodeError as e:
                        response_content = json.dumps(
                            {"error": f"Invalid JSON: {str(e)}"}
                        )
                        conversation.append_message(
                            {
                                "role": "tool",
                                "tool_call_id": tool_call_id,
                                "content": response_content,
                            }
                        )
                        continue

                    handler = TOOLS_REGISTRY.get(function_name)
                    if not handler:
                        response_content = json.dumps({"error": "Function not found"})
                    else:
                        try:
                            result = handler(function_args)
                            response_content = json.dumps(result)
                        except Exception as e:
                            response_content = json.dumps({"error": str(e)})

                    # Save the tool response to conversation
                    conversation.append_message(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": response_content,
                        }
                    )

                except Exception as e:
                    logger.error(f"Error processing tool call {tool_call_id}: {e}")
                    conversation.append_message(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call_id,
                            "content": json.dumps({"error": str(e)}),
                        }
                    )

            messages_for_gpt = [
                msg.model_dump(exclude_none=True) if hasattr(msg, "model_dump") else msg
                for msg in conversation.conversation
            ]

            # Make final API call with complete message history
            logger.info(f"Sending {len(messages_for_gpt)} messages to GPT")
            return self.call_gpt(messages=messages_for_gpt)

        except Exception as e:
            logger.error(f"Error handling function calls: {e}")
            return {"error": str(e)}

    def handle_ai_response(  # noqa: C901
        self,
        response: ChatCompletion,
        conversation: FirestoreConversationModel,
    ) -> str:
        """Process AI response and manage conversation state."""
        try:
            if isinstance(response, dict) and "error" in response:
                logger.error(f"Error in response: {response['error']}")
                return "Desculpe, ocorreu um erro ao processar sua solicitação."

            choices = response.choices
            if not choices:
                return "Desculpe, não consegui processar sua mensagem."

            message_choice = choices[0].message

            if message_choice.tool_calls:
                # Save the assistant's tool calls message
                tool_calls_serialized = [
                    {
                        "id": tool_call.id,
                        "function": {
                            "arguments": tool_call.function.arguments,
                            "name": tool_call.function.name,
                        },
                        "type": tool_call.type,
                    }
                    for tool_call in message_choice.tool_calls
                ]

                conversation.append_message(
                    {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": tool_calls_serialized,
                    }
                )

                # Handle function calls and save responses
                new_response = self.handle_function_call(
                    response_message=message_choice,
                    conversation=conversation,
                )

                if isinstance(new_response, dict) and "error" in new_response:
                    logger.error(f"Function call error: {new_response['error']}")
                    return "Desculpe, ocorreu um erro ao processar sua solicitação."

                if not new_response.choices:
                    return "Desculpe, não obtive uma resposta válida."

                final_message = new_response.choices[0].message.content
                if final_message:
                    # Save the final assistant message
                    conversation.append_message(
                        {"role": "assistant", "content": final_message}
                    )
                    return final_message

                return "Desculpe, não consegui gerar uma resposta apropriada."

            # Handle regular message without function calls
            content = message_choice.content
            if content:
                conversation.append_message({"role": "assistant", "content": content})
                return content

            return "Desculpe, não consegui gerar uma resposta."

        except Exception as e:
            logger.error(f"Error processing AI response: {e}", exc_info=True)
            return "Desculpe, ocorreu um erro inesperado."

    def generate_response(
        self,
        conversation_model: FirestoreConversationModel,
    ) -> str:
        try:
            logger.info(conversation_model.conversation)
            response = self.call_gpt(messages=conversation_model.conversation)
            logger.info(f"AI agent response: {response}")

            return self.handle_ai_response(response, conversation_model)

        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
            raise e
