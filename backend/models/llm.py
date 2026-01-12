from pydantic import BaseModel, Field
from models.common import DifficultyLevel
from enum import Enum

class ConfidenceLevel(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class QuestionAction(Enum):
    ASK_FOLLOWUP = "ASK_FOLLOWUP" # Core concept missing, Answer shallow, Clarification needed
    MOVE_TO_NEXT_QUESTION = "MOVE_TO_NEXT_QUESTION" # Answer is sufficient, Skill coverage achieved
    END_INTERVIEW = "END_INTERVIEW"  # All required skills covered, Time / question limit reached

class Question(BaseModel):
    id: str
    text: str  # The spoken/conversational question
    type: str  # "main" or "followup"
    expected_concepts: list[str]
    skill: str
    difficulty: DifficultyLevel | None = None
    is_coding: bool = False  # True if this requires writing code
    problem_statement: str | None = None  # For coding questions: displayed separately in UI

class QuestionRef(BaseModel):
    question_id: str
    parent_question_id: str | None = None
    question_type: str

class QuestionEvaluation(BaseModel):
    question_ref: QuestionRef
    skill: str
    correctness_score: float = Field(ge=0, le=1)
    depth_score: float = Field(ge=0, le=1)
    communication_score: float = Field(ge=0, le=1)
    observed_concepts: list[str]
    missing_concepts: list[str]
    confidence_level: ConfidenceLevel
    notes: str | None = None


class LLM_Response(BaseModel):
    action: QuestionAction # All

    # Always present: evaluation of the LAST user response
    evaluation: QuestionEvaluation 

    # Present only when ASK_FOLLOWUP or MOVE_TO_NEXT_QUESTION
    next_question: Question | None = None 

    # Optional explanation for audit/debug
    reason: str | None = None


class PrePlanner(BaseModel): # LLM Preplans the topics based on the [JD + Resume]
    serial: int
    skill: str
    difficulty: DifficultyLevel