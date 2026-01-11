"""Main resume parser facade with unified API."""

import re
import logging
from typing import Dict, Any, Optional

from .models import ResumeData, ContactInfo, Education, Experience
from .contact import extract_contact_info
from .education import extract_education
from .experience import extract_experience
from .skills import extract_skills
from .projects import extract_projects
from .coding_profiles import extract_coding_profiles
from .certifications import extract_certifications
from .achievements import extract_achievements
from .links import extract_links
from .summary import extract_summary
from .readers import extract_text, detect_file_type


logger = logging.getLogger(__name__)


class ResumeParser:
    """Unified resume parser with modular extraction components.

    This class provides a clean API for parsing resumes from various file formats
    (PDF, DOCX, TXT) and extracting structured information.

    Usage:
        parser = ResumeParser()
        result = parser.parse_file("resume.pdf")
        print(result.contact.email)
        print(result.skills)
    """

    def parse_file(self, file_path: str) -> ResumeData:
        """Parse a resume file and extract structured data.

        Args:
            file_path: Path to the resume file (PDF, DOCX, or TXT)

        Returns:
            ResumeData object with all extracted information

        Raises:
            ValueError: If file type is not supported
            FileNotFoundError: If file does not exist
        """
        text = extract_text(file_path)
        return self.parse_text(text)

    def parse_text(self, text: str) -> ResumeData:
        """Parse resume text and extract structured data.

        Args:
            text: Raw resume text

        Returns:
            ResumeData object with all extracted information
        """
        if not text:
            return ResumeData()

        contact = extract_contact_info(text)
        education = extract_education(text)
        experience = extract_experience(text)
        skills_list = extract_skills(text)
        projects_list = extract_projects(text)
        coding_profiles_list = extract_coding_profiles(text)
        certifications_list = extract_certifications(text)
        achievements_list = extract_achievements(text)
        links = extract_links(text)
        summary = extract_summary(text)
        role = self._extract_role(text)
        notice_period = self._extract_notice_period(text)

        return ResumeData(
            contact=contact,
            skills=skills_list,
            experience=experience,
            education=education,
            projects=projects_list,
            coding_profiles=coding_profiles_list,
            certifications=certifications_list,
            achievements=achievements_list,
            links=links,
            summary=summary,
            role=role,
            notice_period=notice_period,
            raw_text=text,
        )

    def _extract_role(self, text: str) -> str:
        """Extract current role/position from resume text."""
        role_pattern = (
            r'(?:^|\n)(?:.*?)(Software Engineer|Developer|Programmer|Data Scientist|'
            r'Product Manager|Project Manager|UX Designer|UI Designer|DevOps Engineer|'
            r'QA Engineer|System Administrator|Database Administrator|Full Stack|'
            r'Backend Developer|Frontend Developer|ML Engineer|Data Engineer)'
        )
        match = re.search(role_pattern, text[:500], re.IGNORECASE)
        if match:
            return match.group(1)
        return ""

    def _extract_notice_period(self, text: str) -> str:
        """Extract notice period from resume text."""
        notice_pattern = (
            r'(?:notice\s*period|joining\s*time)(?:\s*:)?\s*'
            r'(\d+\+?\s*(?:days|weeks|months|immediate))'
        )
        match = re.search(notice_pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
        return ""


# Convenience functions for backward compatibility
def parse_resume(file_path: str) -> Dict[str, Any]:
    """Parse a resume file and return a dictionary.

    Convenience function for backward compatibility.

    Args:
        file_path: Path to the resume file

    Returns:
        Dictionary with extracted information
    """
    parser = ResumeParser()
    result = parser.parse_file(file_path)
    return result.to_dict()


def parse_resume_text(text: str) -> Dict[str, Any]:
    """Parse resume text and return a dictionary.

    Convenience function for backward compatibility.

    Args:
        text: Raw resume text

    Returns:
        Dictionary with extracted information
    """
    parser = ResumeParser()
    result = parser.parse_text(text)
    return result.to_dict()


# Aliases for backward compatibility with test.py
def extract_info_from_pdf(pdf_path: str) -> Dict[str, Any]:
    """Extract information from a PDF resume.

    Backward-compatible function matching the original test.py API.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Dictionary with extracted information
    """
    return parse_resume(pdf_path)


def extract_info_from_docx(docx_path: str) -> Dict[str, Any]:
    """Extract information from a DOCX resume.

    Backward-compatible function matching the original test.py API.

    Args:
        docx_path: Path to the DOCX file

    Returns:
        Dictionary with extracted information
    """
    return parse_resume(docx_path)


def extract_candidate_info(text: str) -> Dict[str, Any]:
    """Extract candidate information from resume text.

    Backward-compatible function matching the original test.py API.

    Args:
        text: Raw resume text

    Returns:
        Dictionary with extracted information
    """
    return parse_resume_text(text)
