"""Data models and types for the resume parser."""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class FileType(Enum):
    """Supported file types for parsing."""
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"


@dataclass
class Education:
    """Education information extracted from resume."""
    college_name: str = ""
    department: str = ""
    cgpa: str = ""
    passout_year: str = ""

    def to_dict(self) -> dict:
        return {
            "college_name": self.college_name,
            "department": self.department,
            "cgpa": self.cgpa,
            "passout_year": self.passout_year,
        }


@dataclass
class Experience:
    """Work experience information extracted from resume."""
    companies: List[str] = field(default_factory=list)
    roles: List[str] = field(default_factory=list)
    total_years: float = 0.0

    def to_dict(self) -> dict:
        return {
            "companies": self.companies,
            "roles": self.roles,
            "total_years": self.total_years,
        }


@dataclass
class ContactInfo:
    """Contact information extracted from resume."""
    name: str = ""
    email: str = ""
    phone: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
        }


@dataclass
class ResumeData:
    """Complete parsed resume data."""
    contact: ContactInfo = field(default_factory=ContactInfo)
    skills: List[str] = field(default_factory=list)
    experience: Experience = field(default_factory=Experience)
    education: Education = field(default_factory=Education)
    projects: List = field(default_factory=list)  # List of Project objects
    coding_profiles: List = field(default_factory=list)  # List of CodingProfile objects
    certifications: List = field(default_factory=list)  # List of Certification objects
    achievements: List = field(default_factory=list)  # List of Achievement objects
    links: Any = None  # SocialLinks object
    summary: str = ""
    role: str = ""
    notice_period: str = ""
    raw_text: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.contact.name,
            "email": self.contact.email,
            "phone": self.contact.phone,
            "skills": self.skills,
            "experience": self.experience.to_dict(),
            "education": self.education.to_dict(),
            "projects": [p.to_dict() for p in self.projects],
            "coding_profiles": [cp.to_dict() for cp in self.coding_profiles],
            "certifications": [c.to_dict() for c in self.certifications],
            "achievements": [a.to_dict() for a in self.achievements],
            "links": self.links.to_dict() if self.links else {},
            "summary": self.summary,
            "role": self.role,
            "notice_period": self.notice_period,
            "raw_text": self.raw_text,
        }
