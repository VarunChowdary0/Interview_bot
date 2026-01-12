from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime

from models.job import JobData


class ResumeUploadRequest(BaseModel):
    """Request for resume upload - file handled separately via UploadFile."""
    pass


class CreateInterviewRequest(BaseModel):
    """Request to create a new interview session."""
    resume_session_id: Optional[str] = None  # If resume already uploaded
    resume_data: Optional[dict[str, Any]] = None  # Or provide resume data directly
    job_data: JobData  # Job description data (required)


class CandidateResponseRequest(BaseModel):
    """Request containing candidate's response to a question."""
    response: str = Field(..., min_length=1, max_length=10000)
    timestamp: Optional[datetime] = None


class EndInterviewRequest(BaseModel):
    """Request to end interview early."""
    reason: Optional[str] = None
