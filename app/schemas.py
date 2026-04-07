import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from enum import Enum


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: Optional[uuid.UUID] = None


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class UserOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    created_at: datetime

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyResetCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6)
    new_password: str = Field(min_length=8)


class MessageResponse(BaseModel):
    message: str


class CrawlStatusEnum(str, Enum):
    pending = "pending"
    crawling = "crawling"
    summarizing = "summarizing"
    completed = "completed"
    failed = "failed"


class CrawlJobOut(BaseModel):
    id: uuid.UUID
    url: str
    status: CrawlStatusEnum
    summary: Optional[str]
    pdf_path: Optional[str]
    created_at: datetime
    finished_at: Optional[datetime]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class CrawlRequest(BaseModel):
    url: str


class DocumentOut(BaseModel):
    id: uuid.UUID
    title: str
    source_url: str
    summary: str
    pdf_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class ChatRequest(BaseModel):
    question: str = Field(min_length=1)
    document_ids: list[uuid.UUID] | None = None


class ChatResponse(BaseModel):
    answer: str


class TaskStatus(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class GroupCreate(BaseModel):
    name: str
    description: Optional[str] = None


class GroupUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class GroupOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class TaskCreate(BaseModel):
    title: str
    description: Optional[str] = None
    due_date: Optional[datetime] = None


class TaskUpdate(BaseModel):
    status: TaskStatus
    description: Optional[str] = None


class TaskOut(BaseModel):
    id: uuid.UUID
    title: str
    description: Optional[str]
    status: TaskStatus
    due_date: Optional[datetime]
    created_at: datetime
    group_id: uuid.UUID

    class Config:
        from_attributes = True


class MemberAdd(BaseModel):
    user_identifier: str  # Can be email or user ID


class MemberOut(BaseModel):
    id: uuid.UUID
    email: EmailStr
    role: str

    class Config:
        from_attributes = True



class NotificationOut(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    message: str
    is_read: bool
    created_at: datetime
    group_id: Optional[uuid.UUID]
    membership_id: Optional[uuid.UUID]

    class Config:
        from_attributes = True


class InvitationResponse(BaseModel):
    accept: bool  # True to accept, False to reject



class MessageCreate(BaseModel):
    message: str = Field(min_length=1)


class MessageOut(BaseModel):
    id: uuid.UUID
    user_email: EmailStr
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


class TypingUpdate(BaseModel):
    is_typing: bool



class ShareDocumentRequest(BaseModel):
    group_id: uuid.UUID


class SharedDocumentOut(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    group_id: uuid.UUID
    shared_by_id: uuid.UUID
    shared_at: datetime

    class Config:
        from_attributes = True


class SharedDocumentDetail(BaseModel):
    id: uuid.UUID
    title: str
    source_url: str
    pdf_path: str
    created_at: datetime
    shared_at: datetime
    shared_by_email: EmailStr

    class Config:
        from_attributes = True
