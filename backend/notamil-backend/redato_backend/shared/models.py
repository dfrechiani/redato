from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator
from redato_backend.shared.logger import logger


@dataclass
class ErrorDetailModel:
    description: str
    snippet: str
    error_type: str
    suggestion: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # type: ignore


@dataclass
class AnalysisResultsModel:
    detailed_analysis: Dict[str, Any] = field(default_factory=dict)
    grades: Dict[str, int] = field(default_factory=dict)
    justifications: Dict[str, str] = field(default_factory=dict)
    errors: Dict[str, List[ErrorDetailModel]] = field(default_factory=dict)
    overall_grade: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)  # type: ignore


class MessageContent(BaseModel):
    type: str
    text: Optional[str] = None
    image_url: Optional[Dict[str, str]] = None


class ToolCall(BaseModel):
    id: str
    function: Dict[str, str]
    type: str = "function"


class ConversationMessage(BaseModel):
    role: str
    content: Optional[Union[str, List[MessageContent]]] = None
    tool_call_id: Optional[str] = Field(default=None, exclude=True)
    tool_calls: Optional[List[ToolCall]] = Field(default=None, exclude=True)
    name: Optional[str] = Field(default=None, exclude=True)  # For tool messages

    @field_validator("content", mode="before")
    def validate_content(cls, v):
        # Skip validation if content is None and we have tool_calls
        if v is None and "tool_calls" in cls.model_fields:
            return None
        return v

    def model_dump(self, *args, **kwargs):
        data = super().model_dump(*args, **kwargs)

        if self.tool_call_id is not None:
            data["tool_call_id"] = self.tool_call_id

        if self.tool_calls:
            data["tool_calls"] = [
                {"id": tc.id, "type": tc.type, "function": tc.function}
                for tc in self.tool_calls
            ]

        if self.name is not None:
            data["name"] = self.name

        return {k: v for k, v in data.items() if v is not None}

    class Config:
        extra = "allow"
        validate_assignment = True


class FirestoreConversationModel(BaseModel):
    conversation: List[ConversationMessage] = Field(default_factory=list)
    status: str = Field(default="AI")
    status_expiration: Optional[datetime] = None
    timestamp: Optional[datetime] = None
    expirationTime: datetime

    @field_validator("status")
    def validate_status(cls, v):
        if v not in ["AI", "admin"]:
            raise ValueError("status must be 'AI' or 'admin'")
        return v

    @property
    def is_admin_mode(self) -> bool:
        return self.status == "admin"

    @property
    def is_admin_expired(self) -> bool:
        if not self.is_admin_mode or not self.status_expiration:
            return False
        return datetime.now(timezone.utc) > self.status_expiration

    @classmethod
    def from_firestore(cls, data: Dict[str, Any]) -> "FirestoreConversationModel":
        if not data:
            return cls(
                conversation=[],
                status="AI",
                expirationTime=datetime.now(timezone.utc),
            )
        return cls(**data)

    def to_firestore(self) -> Dict[str, Any]:
        return {
            "conversation": [
                msg.model_dump(exclude_none=True) for msg in self.conversation
            ],
            "status": self.status,
            "status_expiration": self.status_expiration,
            "timestamp": self.timestamp,
            "expirationTime": self.expirationTime,
        }

    def append_message(self, message: Dict[str, Any]) -> None:
        try:
            # Handle tool_calls specifically
            if "tool_calls" in message:
                # Ensure the tool_calls are properly formatted
                tool_calls = [
                    (
                        ToolCall(
                            id=tool_call.get("id"),
                            type=tool_call.get("type", "function"),
                            function={
                                "name": tool_call.get("function", {}).get("name", ""),
                                "arguments": tool_call.get("function", {}).get(
                                    "arguments", "{}"
                                ),
                            },
                        )
                        if isinstance(tool_call, dict)
                        else tool_call
                    )
                    for tool_call in message["tool_calls"]
                ]
                message["tool_calls"] = tool_calls

            conv_message = ConversationMessage(**message)
            self.conversation.append(conv_message)

        except Exception as e:
            logger.error(f"Error appending message: {e}", exc_info=True)
            raise

    def set_admin_mode(self, duration_hours: int = 1) -> None:
        self.status = "admin"
        self.status_expiration = datetime.now(timezone.utc) + timedelta(
            hours=duration_hours
        )

    def set_ai_mode(self) -> None:
        self.status = "AI"
        self.status_expiration = None


class UserInformationModel(BaseModel):
    name: Optional[str] = Field(None, alias="name_of_the_person_you_are_talking_to")
    whatsapp_number: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name_of_the_person_you_are_talking_to": self.name,
            "whatsapp_number": self.whatsapp_number,
        }


class AIResponsePayloadModel(BaseModel):
    instance_id: str
    client_id: str
    chat_id: str
    category: str
    user_name: Optional[str] = None

    @property
    def user_information(self) -> UserInformationModel:
        return UserInformationModel(
            name=self.user_name,
            whatsapp_number=self.chat_id,
        )


class TutorRequest(BaseModel):
    user_id: str
    essay_id: str
    errors: List[str]
    competency: str
    message: str
