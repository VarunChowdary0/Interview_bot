"""Certification extraction from resume text."""

import re
from typing import List
from dataclasses import dataclass


@dataclass
class Certification:
    """A certification extracted from resume."""
    name: str = ""
    issuer: str = ""
    date: str = ""
    credential_id: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "issuer": self.issuer,
            "date": self.date,
            "credential_id": self.credential_id,
        }


# Known certification issuers
KNOWN_ISSUERS = [
    "AWS", "Amazon Web Services", "Google", "Google Cloud", "Microsoft", "Azure",
    "IBM", "Oracle", "Cisco", "CompTIA", "Red Hat", "VMware", "Salesforce",
    "HackerRank", "Coursera", "Udemy", "LinkedIn", "LinkedIn Learning",
    "edX", "Udacity", "FreeCodeCamp", "Codecademy", "Meta", "Facebook",
    "NPTEL", "NASSCOM", "NIIT", "Simplilearn", "Great Learning",
]

# Common certification keywords
CERT_KEYWORDS = [
    "certified", "certification", "certificate", "professional",
    "associate", "specialist", "practitioner", "developer", "architect",
    "administrator", "engineer", "analyst", "expert", "master",
]


def _clean_cert_name(name: str) -> str:
    """Clean and normalize certification name."""
    # Remove leading bullets, dashes, numbers
    name = re.sub(r'^[\s•\-*>◦○▪▸\d.)+]+', '', name)
    # Remove trailing punctuation
    name = re.sub(r'[\s:\-,]+$', '', name)
    # Clean up whitespace
    name = ' '.join(name.split())
    return name.strip()


def _extract_issuer(text: str) -> str:
    """Extract issuer from certification text."""
    # Check for known issuers
    for issuer in KNOWN_ISSUERS:
        if re.search(rf'\b{re.escape(issuer)}\b', text, re.IGNORECASE):
            return issuer

    # Try pattern like "by <Issuer>" or "from <Issuer>"
    match = re.search(r'(?:by|from|issued by|powered by)\s+([A-Z][A-Za-z\s&]+?)(?:[,.\n]|$)', text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    return ""


def _extract_date(text: str) -> str:
    """Extract date from certification text."""
    # Month Year pattern
    match = re.search(
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{4}',
        text, re.IGNORECASE
    )
    if match:
        return match.group(0)

    # Year only
    match = re.search(r'\b(20\d{2})\b', text)
    if match:
        return match.group(1)

    return ""


def _extract_credential_id(text: str) -> str:
    """Extract credential ID from certification text."""
    match = re.search(
        r'(?:Credential\s*ID|Certificate\s*ID|ID)\s*:?\s*([A-Za-z0-9\-]+)',
        text, re.IGNORECASE
    )
    if match:
        return match.group(1)
    return ""


def extract_certifications(text: str) -> List[Certification]:
    """Extract certifications from resume text.

    Looks for certifications section and parses individual entries.

    Args:
        text: Raw resume text

    Returns:
        List of Certification objects
    """
    certifications: List[Certification] = []

    # Find certifications section
    cert_section = re.search(
        r'(?:^|\n)\s*(?:CERTIFICATIONS?|CERTIFICATES?|PROFESSIONAL CERTIFICATIONS?|'
        r'LICENSES?\s*(?:&|AND)?\s*CERTIFICATIONS?|CREDENTIALS?)\s*:?[\t ]*\n'
        r'(.*?)(?=\n\s*(?:EDUCATION|SKILLS|EXPERIENCE|WORK|EMPLOYMENT|'
        r'PROJECTS?|ACHIEVEMENTS?|PUBLICATIONS?|LANGUAGES?|SUMMARY|'
        r'ABOUT|INTERESTS?|HOBBIES?|LEADERSHIP|INTERNSHIPS?|AWARDS?|REFERENCES?)\b|$)',
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if not cert_section:
        # Try to find inline certifications
        cert_section = re.search(
            r'(?:INTERNSHIPS?\s*(?:&|AND)?\s*)?CERTIFICATES?\s*:?[\t ]*\n'
            r'(.*?)(?=\n\s*[A-Z]{2,}|\Z)',
            text,
            re.IGNORECASE | re.DOTALL,
        )

    if not cert_section:
        return certifications

    section_text = cert_section.group(1)
    lines = section_text.split('\n')

    current_cert = None
    current_lines = []

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Check if this starts a new certification entry
        # Look for bullet points or certification-like names
        is_new_entry = (
            re.match(r'^[•\-*>◦○▪▸]', line) or
            re.match(r'^[A-Z][A-Za-z\s]+(?:Certification|Certificate)\b', line, re.IGNORECASE) or
            any(issuer.lower() in line.lower() for issuer in KNOWN_ISSUERS[:10])
        )

        if is_new_entry and current_lines:
            # Process previous certification
            full_text = ' '.join(current_lines)
            cert = Certification(
                name=_clean_cert_name(current_lines[0]),
                issuer=_extract_issuer(full_text),
                date=_extract_date(full_text),
                credential_id=_extract_credential_id(full_text),
            )
            if cert.name:
                certifications.append(cert)
            current_lines = []

        current_lines.append(line)

    # Process last certification
    if current_lines:
        full_text = ' '.join(current_lines)
        cert = Certification(
            name=_clean_cert_name(current_lines[0]),
            issuer=_extract_issuer(full_text),
            date=_extract_date(full_text),
            credential_id=_extract_credential_id(full_text),
        )
        if cert.name:
            certifications.append(cert)

    return certifications
