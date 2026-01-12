from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import uuid4

from models.common import DifficultyLevel


class SkillAssessment(BaseModel):
    """Assessment of a single skill from the interview."""
    skill: str
    questions_asked: int
    average_correctness: float = Field(ge=0, le=1)
    average_depth: float = Field(ge=0, le=1)
    average_communication: float = Field(ge=0, le=1)
    overall_score: float = Field(ge=0, le=1)
    difficulty_reached: DifficultyLevel
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class InterviewSummary(BaseModel):
    """High-level summary of the interview."""
    total_questions: int
    total_followups: int
    duration_minutes: float
    topics_covered: list[str]
    overall_score: float = Field(ge=0, le=1)
    pass_status: bool
    recommendation: str  # "Strong Hire", "Hire", "Maybe", "No Hire"


class InterviewReport(BaseModel):
    """Complete interview report."""
    report_id: str = Field(default_factory=lambda: str(uuid4()))
    session_id: str

    # Candidate info
    candidate_name: str
    candidate_email: str

    # Job info
    job_title: str
    company_name: str

    # Timestamps
    interview_date: datetime
    generated_at: datetime = Field(default_factory=datetime.utcnow)

    # Assessment details
    skill_assessments: list[SkillAssessment] = Field(default_factory=list)
    summary: InterviewSummary

    # Raw data for audit
    conversation_history: list[dict[str, Any]] = Field(default_factory=list)
    all_evaluations: list[dict[str, Any]] = Field(default_factory=list)

    # AI-generated insights
    strengths_summary: str
    areas_for_improvement: str
    hiring_recommendation: str
    detailed_feedback: Optional[str] = None
