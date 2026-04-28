import re
from enum import Enum
from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class UserRole(str, Enum):
    STUDENT = "student"
    PROFESSOR = "professor"
    SCHOOL_ADMIN = "school_admin"
    SYSTEM_ADMIN = "system_admin"


class UserCreate(BaseModel):
    email: EmailStr
    password: str
    name: str
    role: UserRole

    @field_validator("password")
    def validate_password(cls, v):
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"[0-9]", v):
            raise ValueError("Password must contain at least one digit")
        return v


class StudentCreate(BaseModel):
    user_id: str
    class_id: str
    school_id: str


class ProfessorCreate(BaseModel):
    user_id: str
    school_id: str
    class_id: str


class ClassCreate(BaseModel):
    name: str
    school_id: str
    professor_id: Optional[str] = None
