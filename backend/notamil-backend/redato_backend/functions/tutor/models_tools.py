from pydantic import BaseModel, Field
from typing import List, Dict, Any


class AgentTools(BaseModel):
    tools: List[Dict[str, Any]] = Field(default_factory=lambda: [{}])

    class Config:
        extra = "allow"
