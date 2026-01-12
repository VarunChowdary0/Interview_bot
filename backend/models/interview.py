from enum import Enum
from pydantic import BaseModel, Field
from typing import Optional, Any
from datetime import datetime
from uuid import uuid4


class InterviewState(Enum):
    """Interview lifecycle states."""
    NOT_STARTED = "NOT_STARTED"
    GREETING = "GREETING"
    PREPLANNING = "PREPLANNING"
    QUESTIONING = "QUESTIONING"
    FOLLOW_UP = "FOLLOW_UP"
    TRANSITIONING = "TRANSITIONING"
    CONCLUDING = "CONCLUDING"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class ChatRole(Enum):
    """Role of the message sender."""
    SYSTEM = "system"
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"


class ChatMessage(BaseModel):
    """A single message in the interview conversation."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    role: ChatRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[dict[str, Any]] = None  # For question_id, evaluation, etc.


class InterviewProgress(BaseModel):
    """Current progress of the interview."""
    questions_asked: int
    max_questions: int
    topics_completed: int
    total_topics: int
    current_topic_index: int
    current_skill: Optional[str] = None


class InterviewSession(BaseModel):
    """Complete interview session state."""
    session_id: str = Field(default_factory=lambda: str(uuid4()))
    state: InterviewState = InterviewState.NOT_STARTED

    # Input data (stored as dict for flexibility)
    resume_data: Optional[dict[str, Any]] = None
    job_data: Optional[dict[str, Any]] = None

    # Preplanned topics (list of PrePlanner dicts)
    preplanned_topics: list[dict[str, Any]] = Field(default_factory=list)
    current_topic_index: int = 0

    # Question tracking
    current_question: Optional[dict[str, Any]] = None
    questions_asked: int = 0
    followups_for_current: int = 0

    # Conversation history
    messages: list[ChatMessage] = Field(default_factory=list)

    # Evaluations collected (list of QuestionEvaluation dicts)
    evaluations: list[dict[str, Any]] = Field(default_factory=list)

    # LLM call logs (for cost/usage tracking)
    llm_logs: list[dict[str, Any]] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None

    def get_progress(self) -> InterviewProgress:
        """Get current interview progress."""
        max_questions = 10
        if self.job_data and "question_policy" in self.job_data:
            max_questions = self.job_data["question_policy"].get("max_questions", 10)

        current_skill = None
        if self.preplanned_topics and self.current_topic_index < len(self.preplanned_topics):
            current_skill = self.preplanned_topics[self.current_topic_index].get("skill")

        return InterviewProgress(
            questions_asked=self.questions_asked,
            max_questions=max_questions,
            topics_completed=self.current_topic_index,
            total_topics=len(self.preplanned_topics),
            current_topic_index=self.current_topic_index,
            current_skill=current_skill,
        )

    def add_message(self, role: ChatRole, content: str, metadata: Optional[dict] = None) -> ChatMessage:
        """Add a message to the conversation history."""
        message = ChatMessage(role=role, content=content, metadata=metadata)
        self.messages.append(message)
        return message

    def add_evaluation(self, evaluation: dict[str, Any]) -> None:
        """Add an evaluation to the session."""
        self.evaluations.append(evaluation)
