from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

from models.interview import InterviewState, InterviewProgress, ChatMessage


class ErrorResponse(BaseModel):
    """Standard error response."""
    error_code: str
    message: str
    details: Optional[dict[str, Any]] = None


class ResumeUploadResponse(BaseModel):
    """Response after uploading and parsing a resume."""
    session_id: str
    resume_data: dict[str, Any]
    parsed_at: datetime = Field(default_factory=datetime.utcnow)


class InterviewSessionResponse(BaseModel):
    """Response when creating an interview session."""
    session_id: str
    state: InterviewState
    created_at: datetime


class InterviewMessageResponse(BaseModel):
    """Response containing interviewer message and progress."""
    session_id: str
    state: InterviewState
    message: ChatMessage
    progress: InterviewProgress
    is_complete: bool = False


class InterviewStatusResponse(BaseModel):
    """Response for interview status check."""
    session_id: str
    state: InterviewState
    progress: InterviewProgress
    started_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    messages_count: int = 0


class InterviewEndResponse(BaseModel):
    """Response when ending an interview."""
    session_id: str
    state: InterviewState
    ended_at: datetime
    report_available: bool = False
