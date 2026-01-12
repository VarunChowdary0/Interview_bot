from pydantic import BaseModel
from typing import Optional, Dict
from enum import Enum
from models.common import DifficultyLevel

class JobLevel(Enum):
    FRESHER = "FRESHER"
    JUNIOR = "JUNIOR"
    SENIOR = "SENIOR"

class DifficultyPolicy(BaseModel):
    start_level: DifficultyLevel
    max_level: DifficultyLevel
    increase_on_good_answer: bool
    decrease_on_struggle: bool

class QuestionPolicy(BaseModel):
    max_questions: int
    max_followup_per_question: int
    time_limit: int

class EvaluationRubric(BaseModel):
    correctness: float
    depth: float
    communication: float

class PassCriteria(BaseModel):
    minimum_overall_score: float
    mandatory_skills: Optional[list[str]] = []
    minimum_communication_score = float

class JobData(BaseModel):
    company_name: str
    title: str
    description: str
    expirence: str
    level: JobLevel
    responsibilities: Optional[list[str]] = []
    primary_skills: Optional[list[str]] = []
    secondary_have: Optional[list[str]] = []
    soft_skills: Optional[list[str]] = []
    skill_weights: Dict[str, float]
    difficulty_policy: DifficultyPolicy
    question_policy: QuestionPolicy # needed for each question with addionally sending count of completed questions, sent in header
    evaluation_rubric: EvaluationRubric # needed for each question evaluation, sent in header
    pass_criteria: PassCriteria # for final evaluation