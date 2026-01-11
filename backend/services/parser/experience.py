"""Work experience extraction from resume text."""

import re
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

from .models import Experience


# Date parsing constants
MONTH_MAP = {
    'jan': 1, 'january': 1, 'feb': 2, 'february': 2, 'mar': 3, 'march': 3,
    'apr': 4, 'april': 4, 'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
    'aug': 8, 'august': 8, 'sep': 9, 'sept': 9, 'september': 9, 'oct': 10, 'october': 10,
    'nov': 11, 'november': 11, 'dec': 12, 'december': 12
}

# Company suffix pattern
COMPANY_SUFFIX_RE = re.compile(
    r"\b(Inc\.?|LLC|LLP|Ltd\.?|Limited|Pvt\.?|Pvt\.? Ltd\.?|Private Limited|"
    r"Corp\.?|Corporation|Co\.?|GmbH|AG|BV|S\.?A\.?|SAS|PLC|Technologies|"
    r"Technology|Systems|Solutions|Labs|Software|Services)\b"
)

# Role title hints
ROLE_TITLE_HINT = re.compile(
    r"\b(Engineer|Developer|Manager|Architect|Analyst|Consultant|Lead|Director|"
    r"Principal|Staff|Specialist|Administrator|Scientist|Intern|QA Engineer|"
    r"DevOps Engineer|SDE(?:\s*(?:I|II|III))?)\b",
    re.IGNORECASE
)


def _parse_date_token(tok: str) -> Optional[datetime]:
    """Parse a date token into a datetime object."""
    t = tok.strip().lower().strip('. ,;')

    if t in ("present", "current", "till date", "till-date"):
        return datetime.now()

    # Month Year format (Jan 2020)
    m = re.match(r"([a-zA-Z]{3,9})\s+(\d{4})", t)
    if m:
        mon = MONTH_MAP.get(m.group(1)[:3].lower()) or MONTH_MAP.get(m.group(1).lower())
        if mon:
            try:
                return datetime(int(m.group(2)), mon, 1)
            except ValueError:
                return None

    # MM/YYYY or M/YYYY format
    m = re.match(r"(\d{1,2})[\/-](\d{4})", t)
    if m:
        mon = int(m.group(1))
        yr = int(m.group(2))
        if 1 <= mon <= 12:
            try:
                return datetime(yr, mon, 1)
            except ValueError:
                return None

    # YYYY only -> mid-year assumption (July)
    m = re.match(r"(19\d{2}|20\d{2})", t)
    if m:
        try:
            return datetime(int(m.group(1)), 7, 1)
        except ValueError:
            return None

    return None


def _merge_date_ranges(ranges: List[Tuple[datetime, datetime]]) -> List[Tuple[datetime, datetime]]:
    """Merge overlapping date ranges."""
    if not ranges:
        return []

    sorted_ranges = sorted(ranges, key=lambda x: x[0])
    merged = [sorted_ranges[0]]

    for start, end in sorted_ranges[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            if end > last_end:
                merged[-1] = (last_start, end)
        else:
            merged.append((start, end))

    return merged


def _diff_in_months(start: datetime, end: datetime) -> int:
    """Calculate difference in months between two dates (inclusive)."""
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _tidy_company(seg: str) -> str:
    """Clean company name by removing dates and locations."""
    # Remove trailing month-year and 'Present/Current'
    seg = re.split(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\b\s*\d{4}",
        seg, flags=re.IGNORECASE
    )[0]
    seg = re.split(r"\b(?:Present|Current)\b", seg, flags=re.IGNORECASE)[0]

    # Keep base before first comma (drop locations)
    if ',' in seg:
        seg = seg.split(',', 1)[0]

    return seg.strip(' ,-|')


def _extract_company_from_line(ln: str) -> Optional[str]:
    """Extract company name from a single line."""
    # Label-based pattern
    m = re.search(r"(?:Company|Organization|Employer|Client)\s*[:\-]\s*([^\|\-,()]+)", ln, re.IGNORECASE)
    if m:
        return _tidy_company(m.group(1))

    # ' at ' or '@' pattern - improved to capture company after "at"
    m = re.search(r"\b(?:at|@)\s+([A-Z][A-Za-z0-9&().,\- ]{2,})", ln)
    if m:
        seg = re.split(r"\s*(?:\||,| - |\(|from|since|\d{4}|\d{1,2}[\/-]\d{4}|Present|present)\s*", m.group(1))[0]
        return _tidy_company(seg)

    # Dash/pipe split with company suffixes
    if ' - ' in ln or ' | ' in ln or ' – ' in ln or ' — ' in ln:
        parts = re.split(r"\s*(?:[-–—]|\|)\s*", ln)
        for part in parts:
            if COMPANY_SUFFIX_RE.search(part):
                return _tidy_company(part)
        # If no suffix found, check if second part looks like a company (capitalized, not a role)
        if len(parts) >= 2:
            second = parts[1].strip()
            if second and second[0].isupper() and not ROLE_TITLE_HINT.search(second):
                # Check it's not a date
                if not re.match(r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)", second, re.IGNORECASE):
                    return _tidy_company(second)

    # Pattern: "Role, Company" or "Role | Company"
    m = re.search(
        r"(?:Engineer|Developer|Intern|Analyst|Manager|Architect|Consultant|Designer)[,|\s]+([A-Z][A-Za-z0-9&().,\- ]{2,40})",
        ln
    )
    if m:
        company = m.group(1).strip()
        if not ROLE_TITLE_HINT.search(company):
            return _tidy_company(company)

    # Month-year after company-like prefix
    m = re.match(
        r"^([A-Z][A-Za-z0-9&().,\- ]{2,}?)\s+\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\b\s*\d{4}",
        ln, flags=re.IGNORECASE
    )
    if m:
        cand = m.group(1)
        if COMPANY_SUFFIX_RE.search(cand) or len(cand.split()) <= 6:
            return _tidy_company(cand)

    # Internship pattern: "Internship with/at Company"
    m = re.search(r"(?:Internship|Intern)\s+(?:with|at)\s+([A-Z][A-Za-z0-9&().,\- ]{2,})", ln, re.IGNORECASE)
    if m:
        return _tidy_company(m.group(1))

    return None


def _clean_role(role: str) -> str:
    """Remove dates and clean up role string."""
    # Remove month-year patterns
    role = re.sub(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s*\d{0,4}\s*[-–—]?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)?[a-z]*\.?\s*\d{0,4}",
        "", role, flags=re.IGNORECASE
    )
    # Remove standalone month names
    role = re.sub(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\b",
        "", role, flags=re.IGNORECASE
    )
    # Remove year patterns
    role = re.sub(r"\b(?:19|20)\d{2}\b", "", role)
    # Remove Present/Current
    role = re.sub(r"\b(?:Present|Current)\b", "", role, flags=re.IGNORECASE)
    # Clean special characters
    role = role.replace("ÔÇô", " ").replace("–", " ").replace("—", " ")
    # Clean up whitespace and trailing punctuation
    role = re.sub(r"\s+", " ", role).strip(" -–—|,:")
    return role


def _extract_role_from_line(ln: str) -> Optional[str]:
    """Extract role/title from a single line."""
    # Label-based pattern
    m = re.search(r"(?:Role|Position|Title|Designation)\s*[:\-]\s*([^\|\-,()]+)", ln, re.IGNORECASE)
    if m:
        return _clean_role(m.group(1))

    # Before ' at ' or '@'
    m = re.search(r"^([A-Z][A-Za-z/&() \-]{2,60})\s+(?:at|@)\s+", ln)
    if m:
        return _clean_role(m.group(1))

    # Before dash or pipe with title hint
    m = re.match(r"^([A-Z][A-Za-z/&() \-]{2,60})\s*(?:\-|\|)", ln)
    if m and ROLE_TITLE_HINT.search(m.group(1)):
        cand = re.split(r"\s*(?:\bat\b|\|)\s*", m.group(1))[0]
        return _clean_role(cand)

    # Bullet lines with title hint
    m = re.match(r"^[•\-*>]\s*([A-Z][A-Za-z/&() \-]{2,60})", ln)
    if m and ROLE_TITLE_HINT.search(m.group(1)):
        return _clean_role(m.group(1))

    # Generic inline title - improved pattern
    m = re.search(
        r"([A-Z][A-Za-z ]{2,40}?(?:Engineer|Developer|Intern|Analyst|Manager|Architect|Consultant|Designer|Scientist)(?: [A-Za-z]{1,12})?)",
        ln
    )
    if m:
        return _clean_role(m.group(1))

    return None


def _add_unique(lst: List[str], val: str) -> None:
    """Add value to list if unique and non-empty."""
    v = re.sub(r"\s+", " ", val).strip().strip('-,|:')
    if v and v not in lst:
        lst.append(v)


def extract_experience(text: str) -> Experience:
    """Extract work experience information from resume text.

    Finds experience section, parses date ranges, and extracts companies and roles.
    Merges overlapping date ranges to compute total experience in years.

    Args:
        text: Raw resume text

    Returns:
        Experience object with companies, roles, and total_years
    """
    # Find experience section
    exp_sec = re.search(
        r"(?:^|\n)\s*(EXPERIENCE|WORK EXPERIENCE|WORK HISTORY|EMPLOYMENT|"
        r"PROFESSIONAL EXPERIENCE|CAREER HISTORY|CAREER|INTERNSHIP|INTERNSHIPS)\s*:?[\t ]*\n"
        r"(.*?)(?=\n\s*(?:EDUCATION|SKILLS|PROJECTS|CERTIFICATIONS|ACHIEVEMENTS|"
        r"PUBLICATIONS|LANGUAGES|SUMMARY|ABOUT|INTERESTS|HOBBIES|LEADERSHIP)\b|$)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    block = exp_sec.group(2) if exp_sec else text
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]

    # Parse date ranges
    date_sep = r"\s*(?:-|–|—|to|TO|–|—)\s*"
    date_token = r"(?:[A-Za-z]{3,9}\s+\d{4}|\d{1,2}[\/-]\d{4}|(?:19\d{2}|20\d{2})|Present|Current|present|current)"
    range_pat = re.compile(fr"({date_token}){date_sep}({date_token})")

    ranges: List[Tuple[datetime, datetime]] = []
    date_line_idxs: List[int] = []

    for idx, ln in enumerate(lines):
        for m in range_pat.finditer(ln):
            start_dt = _parse_date_token(m.group(1))
            end_dt = _parse_date_token(m.group(2))
            if start_dt and end_dt:
                if end_dt < start_dt:
                    start_dt, end_dt = end_dt, start_dt
                ranges.append((start_dt, end_dt))
                date_line_idxs.append(idx)

    # Calculate total experience
    merged = _merge_date_ranges(ranges)
    total_months = sum(_diff_in_months(s, e) for s, e in merged)

    # Fallback: parse explicit experience statements
    if total_months == 0:
        joined_text = " ".join(lines)
        stmt = re.search(
            r"(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\s*(?:and)?\s*(\d+(?:\.\d+)?)?\s*(?:months?|mos?)?",
            joined_text,
            re.IGNORECASE
        )
        if stmt:
            years = float(stmt.group(1))
            months = float(stmt.group(2)) if stmt.group(2) else 0.0
            total_months = int(round(years * 12 + months))
        else:
            m_only = re.search(r"(\d+(?:\.\d+)?)\s*(?:months?|mos?)", joined_text, re.IGNORECASE)
            if m_only:
                total_months = int(round(float(m_only.group(1))))

    total_years = round(total_months / 12.0, 1) if total_months > 0 else 0.0

    # Extract companies and roles
    companies: List[str] = []
    roles: List[str] = []

    # Pass A: Check lines around date ranges
    for idx in date_line_idxs:
        for neigh in (idx - 1, idx, idx + 1):
            if 0 <= neigh < len(lines):
                ln = lines[neigh]
                comp = _extract_company_from_line(ln)
                if comp:
                    _add_unique(companies, comp)
                role = _extract_role_from_line(ln)
                if role:
                    _add_unique(roles, role)

    # Pass B: Global sweep
    skip_headers = re.compile(
        r"^(EDUCATION|TECHNICAL SKILLS|SKILLS|PROJECTS|CERTIFICATIONS|CODING PROFILES|LEADERSHIP)\b",
        re.IGNORECASE
    )
    for ln in lines:
        if skip_headers.match(ln):
            continue
        comp = _extract_company_from_line(ln)
        if comp:
            _add_unique(companies, comp)
        role = _extract_role_from_line(ln)
        if role:
            _add_unique(roles, role)

    return Experience(
        companies=companies,
        roles=roles,
        total_years=total_years,
    )
