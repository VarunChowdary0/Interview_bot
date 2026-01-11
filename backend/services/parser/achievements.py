"""Achievement extraction from resume text."""

import re
from typing import List
from dataclasses import dataclass


@dataclass
class Achievement:
    """An achievement extracted from resume."""
    description: str = ""
    category: str = ""  # academic, competition, award, recognition

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "category": self.category,
        }


# Achievement indicator keywords
ACHIEVEMENT_KEYWORDS = [
    "rank", "ranked", "top", "first", "second", "third", "winner", "won",
    "awarded", "award", "achieved", "achievement", "secured", "scored",
    "percentile", "topper", "medal", "gold", "silver", "bronze",
    "distinction", "honor", "honours", "merit", "excellence", "outstanding",
    "best", "highest", "selected", "qualified", "finalist", "champion",
    "scholar", "scholarship", "fellowship", "dean's list",
]

# Category patterns
ACADEMIC_PATTERNS = [
    r'(?:top|ranked)\s*\d+%', r'scored?\s*\d+%', r'cgpa', r'gpa',
    r'percentile', r'topper', r'distinction', r'merit',
    r'dean\'?s?\s*list', r'honor\s*roll', r'class\s*rank',
]

COMPETITION_PATTERNS = [
    r'hackathon', r'coding\s*(?:competition|contest)', r'olympiad',
    r'challenge', r'contest', r'competitive', r'programming',
]

AWARD_PATTERNS = [
    r'award', r'medal', r'gold', r'silver', r'bronze', r'prize',
    r'winner', r'won', r'champion',
]


def _categorize_achievement(text: str) -> str:
    """Categorize an achievement based on keywords."""
    text_lower = text.lower()

    for pattern in COMPETITION_PATTERNS:
        if re.search(pattern, text_lower):
            return "competition"

    for pattern in AWARD_PATTERNS:
        if re.search(pattern, text_lower):
            return "award"

    for pattern in ACADEMIC_PATTERNS:
        if re.search(pattern, text_lower):
            return "academic"

    return "recognition"


def _clean_achievement(text: str) -> str:
    """Clean and normalize achievement text."""
    # Remove leading bullets, dashes, numbers
    text = re.sub(r'^[\s•\-*>◦○▪▸\d.)+]+', '', text)
    # Remove trailing punctuation
    text = re.sub(r'[\s:\-,]+$', '', text)
    # Clean up whitespace
    text = ' '.join(text.split())
    return text.strip()


def _is_achievement_line(line: str) -> bool:
    """Check if a line contains achievement-related content."""
    line_lower = line.lower()
    return any(keyword in line_lower for keyword in ACHIEVEMENT_KEYWORDS)


def extract_achievements(text: str) -> List[Achievement]:
    """Extract achievements from resume text.

    Looks for achievements/awards section and also scans education
    section for academic achievements.

    Args:
        text: Raw resume text

    Returns:
        List of Achievement objects
    """
    achievements: List[Achievement] = []
    seen = set()

    # Find dedicated achievements section
    ach_section = re.search(
        r'(?:^|\n)\s*(?:ACHIEVEMENTS?|AWARDS?|HONORS?|HONOURS?|'
        r'AWARDS?\s*(?:&|AND)?\s*ACHIEVEMENTS?|RECOGNITIONS?|ACCOMPLISHMENTS?)\s*:?[\t ]*\n'
        r'(.*?)(?=\n\s*(?:EDUCATION|SKILLS|EXPERIENCE|WORK|EMPLOYMENT|'
        r'PROJECTS?|CERTIFICATIONS?|PUBLICATIONS?|LANGUAGES?|SUMMARY|'
        r'ABOUT|INTERESTS?|HOBBIES?|LEADERSHIP|INTERNSHIPS?|REFERENCES?)\b|$)',
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if ach_section:
        section_text = ach_section.group(1)
        for line in section_text.split('\n'):
            line = line.strip()
            if line and len(line) > 10:
                cleaned = _clean_achievement(line)
                if cleaned and cleaned not in seen:
                    seen.add(cleaned)
                    achievements.append(Achievement(
                        description=cleaned,
                        category=_categorize_achievement(cleaned),
                    ))

    # Also scan education section for academic achievements
    edu_section = re.search(
        r'(?:^|\n)\s*(?:EDUCATION|ACADEMIC)\s*:?[\t ]*\n'
        r'(.*?)(?=\n\s*(?:SKILLS|EXPERIENCE|WORK|EMPLOYMENT|'
        r'PROJECTS?|CERTIFICATIONS?|ACHIEVEMENTS?)\b|$)',
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if edu_section:
        section_text = edu_section.group(1)
        for line in section_text.split('\n'):
            line = line.strip()
            # Look for achievement indicators
            if _is_achievement_line(line) and len(line) > 10:
                # Extract just the achievement part
                match = re.search(
                    r'(?:Academic\s*Achievements?\s*:?\s*)(.+)',
                    line, re.IGNORECASE
                )
                if match:
                    cleaned = _clean_achievement(match.group(1))
                else:
                    cleaned = _clean_achievement(line)

                if cleaned and cleaned not in seen and len(cleaned) > 5:
                    seen.add(cleaned)
                    achievements.append(Achievement(
                        description=cleaned,
                        category="academic",
                    ))

    return achievements
