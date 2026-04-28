from pydantic import BaseModel


class EssayRequestModel(BaseModel):
    user_id: str
    content: str
    theme: str
    request_id: str
    callback_url: str


class EssayProcessingError(Exception):
    pass
