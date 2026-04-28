from typing import Optional
from enum import Enum


from pydantic import BaseModel, EmailStr


class UserRole(str, Enum):
    STUDENT = "student"
    PROFESSOR = "professor"
    SCHOOL_ADMIN = "school_admin"
    SYSTEM_ADMIN = "system_admin"


class UserOut(BaseModel):
    id: int
    email: EmailStr

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str
    user_id: str
    username: str
    role: str
    school_id: Optional[str] = None
    class_id: Optional[str] = None


class UploadEssay(BaseModel):
    user_id: str
    content: str
    theme: Optional[str] = None
    theme_id: Optional[str] = None
    ocr_id: Optional[str] = None


class ThemeCreate(BaseModel):
    name: str
    description: str
    class_id: str
