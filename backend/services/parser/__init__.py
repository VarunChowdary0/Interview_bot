"""Resume Parser Module

A modular resume/CV parser for extracting structured information from PDF, DOCX, and TXT files.

Components:
    - models: Data classes for structured resume data
    - contact: Email, phone, and name extraction
    - education: Education history extraction
    - experience: Work experience extraction
    - skills: Technical skills extraction
    - readers: File format handlers (PDF, DOCX, TXT)
    - parser: Main parser facade

Usage:
    from services.parser import ResumeParser, parse_resume

    # Using the class-based API
    parser = ResumeParser()
    result = parser.parse_file("resume.pdf")
    print(result.contact.email)
    print(result.skills)
    print(result.experience.total_years)

    # Using the function API
    data = parse_resume("resume.pdf")
    print(data["email"])
    print(data["skills"])

    # Backward-compatible functions
    from services.parser import extract_info_from_pdf, extract_info_from_docx
    info = extract_info_from_pdf("resume.pdf")
"""

from .models import (
    FileType,
    Education,
    Experience,
    ContactInfo,
    ResumeData,
)

from .contact import (
    extract_email,
    extract_phone,
    extract_name,
    extract_contact_info,
)

from .education import extract_education

from .experience import extract_experience

from .skills import extract_skills

from .projects import extract_projects, Project

from .coding_profiles import extract_coding_profiles, CodingProfile

from .certifications import extract_certifications, Certification

from .achievements import extract_achievements, Achievement

from .links import extract_links, SocialLinks

from .summary import extract_summary

from .readers import (
    detect_file_type,
    extract_text,
    extract_text_from_pdf,
    extract_text_from_docx,
    extract_text_from_txt,
)

from .parser import (
    ResumeParser,
    parse_resume,
    parse_resume_text,
    # Backward-compatible aliases
    extract_info_from_pdf,
    extract_info_from_docx,
    extract_candidate_info,
)


__all__ = [
    # Models
    "FileType",
    "Education",
    "Experience",
    "ContactInfo",
    "ResumeData",
    # Main parser
    "ResumeParser",
    "parse_resume",
    "parse_resume_text",
    # Individual extractors
    "extract_email",
    "extract_phone",
    "extract_name",
    "extract_contact_info",
    "extract_education",
    "extract_experience",
    "extract_skills",
    "extract_projects",
    "Project",
    "extract_coding_profiles",
    "CodingProfile",
    "extract_certifications",
    "Certification",
    "extract_achievements",
    "Achievement",
    "extract_links",
    "SocialLinks",
    "extract_summary",
    # File readers
    "detect_file_type",
    "extract_text",
    "extract_text_from_pdf",
    "extract_text_from_docx",
    "extract_text_from_txt",
    # Backward-compatible functions
    "extract_info_from_pdf",
    "extract_info_from_docx",
    "extract_candidate_info",
]
