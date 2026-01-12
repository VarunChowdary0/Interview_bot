from pydantic import BaseModel
from typing import Optional, Dict, Any


class Experience(BaseModel):
    companies: list[str]
    roles: list[str]
    total_years: float

class Education(BaseModel):
    college_name: str
    degree: str
    department: str
    cgpa: str
    passout_year: str

class Projects(BaseModel):
    name: str
    description: str
    technologies: list[str]

class CodingProfile(BaseModel):
    platform: str
    username: str
    problems_solved: int
    rank: str
    score: str
    url: str

class Certification(BaseModel):
    name: str
    issuer: str
    date: str
    credential_id: str

class Achievements(BaseModel):
    description: str
    category: str

class Resume(BaseModel):
    name: str
    email: str
    phone: str
    skills: list[str]
    experience: Optional[Experience] = None
    education: Optional[list[Education]] = []
    projects: Optional[list[Projects]] = []
    coding_profiles: Optional[list[CodingProfile]] = [] 
    certifications: Optional[list[Certification]] = []
    achievements: Optional[list[Achievements]] = []
    links: Dict[str, Any]
    summary: str
    role: str
    notice_period: str
    raw_text: str