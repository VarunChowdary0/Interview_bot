"""Education information extraction from resume text."""

import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from .models import Education


logger = logging.getLogger(__name__)


# Degree pattern constants
HIGHER_DEGREE_RE = r"\b(b[\s.\-]*e|b[\s.\-]*tech|be|btech|m[\s.\-]*e|m[\s.\-]*tech|me|mtech|bachelor|master|mba|mca|phd|doctorate)\b"
SCHOOL_DEGREE_RE = r"\b(12th|xii|intermediate|10th|x|ssc|hsc|higher secondary|senior secondary)\b"

DEGREE_PAT = re.compile(
    r"(?i)\b("
    r"b[\s.\-]*e|b[\s.\-]*tech|be|btech|b\.sc|bsc|b\.a|ba|b\.com|bcom|bca|bba|b\.pharm|bpharm|"
    r"m[\s.\-]*e|m[\s.\-]*tech|me|mtech|m\.sc|msc|m\.a|ma|m\.com|mcom|mca|mba|"
    r"phd|doctorate|diploma|bachelor|master|12th|xii|intermediate|10th|x|ssc|hsc"
    r")\b[^\n]*"
)

# Institution patterns
INST_PAT = re.compile(r"(?i)\b([A-Z][A-Za-z&.,()\- ]*?(?:University|Institute|College|School of|School|Academy)[A-Za-z&.,()\- ]*)")
INST_ALT_PAT = re.compile(r"(?i)\b([A-Z][A-Za-z&.,()\- ]{2,}?(?:Institute of|College of|University of)\s+[A-Z][A-Za-z&.\- ]{2,})")
INST_ENG_PAT = re.compile(
    r"(?i)\b("
    r"[A-Z][A-Za-z&.,()\- ]{2,}?"
    r"(?:Institute|College|University)"
    r"[A-Za-z&.,()\- ]{0,60}?"
    r"(?:of\s+)?"
    r"(?:Technology|Engineering|Technological|Engineering\s+and\s+Technology)"
    r"[A-Za-z&.,()\- ]*"
    r")"
)

# Department/branch patterns
DEPT_AFTER_IN_PAT = re.compile(r"(?i)\bin\s+([A-Za-z&/\-\s]{2,60})")
DEPT_AFTER_OF_PAT = re.compile(r"(?i)\b(?:Bachelor|Master|B\.?Tech|M\.?Tech|B\.?E|M\.?E|BSc|MSc|BA|MA|BCA|MCA)\s+of\s+([A-Za-z&/\-\s]{2,60})")
DEPT_PAREN_PAT = re.compile(r"\(([A-Z]{2,6})\)")

# Grade patterns
CGPA_PAT = re.compile(r"(?i)\bCGPA\s*[:\-]?\s*([0-9](?:\.[0-9]{1,2})?(?:\s*/\s*10)?)")
GPA_PAT = re.compile(r"(?i)\bGPA\s*[:\-]?\s*([0-9](?:\.[0-9]{1,2})?(?:\s*/\s*4)?)")
PCT_PAT = re.compile(r"(?i)\b(?:Percentage|Percent|Marks)\s*[:\-]?\s*([0-9]{1,3}(?:\.[0-9]{1,2})?\s*%)")

# Year patterns
YEAR_PAT = re.compile(r"\b(19\d{2}|20\d{2})\b")
YEAR_RANGE_PAT = re.compile(r"\b(19\d{2}|20\d{2})\b\s*(?:-|–|—|to|TO)\s*(Present|Current|present|current|19\d{2}|20\d{2})")


def _clean_value(s: str) -> str:
    """Clean extracted value by removing whitespace and bullet markers."""
    s = re.sub(r"\s+", " ", s)
    s = s.strip().lstrip("•·●◦▪■*-–—>»)\t ")
    s = s.strip(" ,;:-")
    return s.strip()


def _is_school_degree(text: str) -> bool:
    """Check if text contains school-level degree keywords."""
    return bool(re.search(SCHOOL_DEGREE_RE, text, re.IGNORECASE))


def _is_higher_degree(text: str) -> bool:
    """Check if text contains higher education degree keywords."""
    return bool(re.search(HIGHER_DEGREE_RE, text, re.IGNORECASE))


def _get_degree_level(entry_text: str) -> int:
    """Determine degree level: 2=higher education, 1=school, 0=unknown."""
    if _is_higher_degree(entry_text):
        return 2
    elif _is_school_degree(entry_text):
        return 1
    return 0


def _tidy_institution_line(ln: str) -> str:
    """Clean institution name by removing degree/year markers."""
    val = _clean_value(ln)

    # Remove trailing degree/year markers
    val = re.split(
        r"(?i)\b(b[\s.\-]*tech|m[\s.\-]*tech|b[\s.\-]*e|m[\s.\-]*e|bachelor|master|cgpa|gpa|percentage|percent)\b",
        val,
    )[0].strip(" ,;:-")

    # Strip year ranges and standalone years
    val = re.sub(
        r"(?i)\b(19\d{2}|20\d{2})\b\s*(?:-|–|—|to|TO)\s*(?:present|current|19\d{2}|20\d{2})\b",
        " ", val
    )
    val = re.sub(r"\b(19\d{2}|20\d{2})\b", " ", val)
    val = re.sub(r"\s+", " ", val).strip(" ,;:-")

    return val


def _parse_education_entry(block: str) -> Dict[str, str]:
    """Parse a single education entry block."""
    fields = {"college_name": "", "department": "", "cgpa": "", "passout_year": ""}
    lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
    joined = " \n ".join(lines)

    # Extract passout year
    yr_candidates: List[int] = []
    for m in YEAR_RANGE_PAT.finditer(joined):
        end = m.group(2)
        if end.lower() in ("present", "current"):
            yr_candidates.append(datetime.now().year)
        else:
            try:
                yr_candidates.append(int(end))
            except ValueError:
                pass

    if not yr_candidates:
        for y in YEAR_PAT.findall(joined):
            try:
                yr_candidates.append(int(y))
            except ValueError:
                pass

    if yr_candidates:
        fields["passout_year"] = str(max(yr_candidates))

    # Find institution
    fields["college_name"] = _extract_institution(lines, joined)

    # Extract department
    fields["department"] = _extract_department(joined)

    # Extract CGPA/GPA/Percentage
    fields["cgpa"] = _extract_grade(joined)

    return fields


def _extract_institution(lines: List[str], joined: str) -> str:
    """Extract institution name from education entry."""
    inst_marker_pat = re.compile(
        r"(?i)\b(university|institute|college|academy|school|polytechnic|campus)\b"
    )

    # Find degree line index
    deg_idx: Optional[int] = None
    for i, ln in enumerate(lines):
        if DEGREE_PAT.search(ln):
            deg_idx = i
            break

    has_higher_degree = _is_higher_degree(joined)

    def is_schoolish_line(ln: str) -> bool:
        low = ln.lower()
        return _is_school_degree(low) or ("junior" in low)

    # Search around degree line for institution
    if deg_idx is not None:
        for offset in range(1, 5):
            up = deg_idx - offset
            if up >= 0:
                cand = lines[up]
                if inst_marker_pat.search(cand) and not DEGREE_PAT.search(cand):
                    if not (has_higher_degree and is_schoolish_line(cand)):
                        return _tidy_institution_line(cand)

            down = deg_idx + offset
            if down < len(lines):
                cand = lines[down]
                if inst_marker_pat.search(cand) and not DEGREE_PAT.search(cand):
                    if not (has_higher_degree and is_schoolish_line(cand)):
                        return _tidy_institution_line(cand)

    # Try regex patterns on joined text
    inst_matches: List[Tuple[str, int]] = []
    for m in INST_PAT.finditer(joined):
        inst_matches.append((_clean_value(m.group(1)), m.start(1)))
    for m in INST_ALT_PAT.finditer(joined):
        inst_matches.append((_clean_value(m.group(1)), m.start(1)))
    for m in INST_ENG_PAT.finditer(joined):
        inst_matches.append((_clean_value(m.group(1)), m.start(1)))

    if inst_matches:
        # Filter and dedupe
        seen = set()
        deduped = []
        for name, pos in inst_matches:
            key = name.lower()
            if key and key not in seen:
                seen.add(key)
                deduped.append((name, pos))

        if has_higher_degree:
            non_school = [name for name, _ in deduped if not is_schoolish_line(name)]
            if non_school:
                return non_school[-1]

        if deduped:
            return deduped[-1][0]

    return ""


def _extract_department(joined: str) -> str:
    """Extract department/branch from education entry."""
    m_in = DEPT_AFTER_IN_PAT.search(joined)
    if m_in:
        dept = _clean_value(m_in.group(1))
        dept = re.split(r"\b(?:University|Institute|College|School|,|\|| - )\b", dept)[0].strip()
        dept = re.sub(r"(?i)\s*(?:cgpa|gpa|percentage|percent|marks|grade)\b.*$", "", dept).strip()
        return dept

    m_of = DEPT_AFTER_OF_PAT.search(joined)
    if m_of:
        dept = _clean_value(m_of.group(1))
        dept = re.sub(r"(?i)\s*(?:cgpa|gpa|percentage|percent|marks|grade)\b.*$", "", dept).strip()
        return dept

    m_paren = DEPT_PAREN_PAT.search(joined)
    if m_paren:
        return m_paren.group(1).strip()

    return ""


def _extract_grade(joined: str) -> str:
    """Extract CGPA, GPA, or percentage from education entry."""
    # Normalize comma decimals
    joined_cgpa = re.sub(r"(?<=\d),(?=\d)", ".", joined)

    # Try various patterns in order of specificity
    patterns = [
        (CGPA_PAT, lambda m: _clean_value(m.group(1)).replace(",", ".")),
        (GPA_PAT, lambda m: _clean_value(m.group(1)).replace(",", ".")),
        (PCT_PAT, lambda m: _clean_value(m.group(1))),
    ]

    for pat, extractor in patterns:
        m = pat.search(joined_cgpa)
        if m:
            return extractor(m)

    # Fallback patterns
    # Grade like '8.65/10'
    m = re.search(r"\b(10(?:[\.,]0{1,2})?|[0-9](?:[\.,][0-9]{1,2})?)\s*/\s*10(?:[\.,]0{1,2})?\b", joined_cgpa)
    if m:
        return _clean_value(m.group(1)).replace(",", ".")

    # Value after CGPA/GPA label
    m = re.search(r"(?i)(?:cgpa|gpa|sgpa)\s*[:\-]?\s*([0-9](?:[\.,][0-9]{1,2})?)\b", joined_cgpa)
    if m:
        return _clean_value(m.group(1)).replace(",", ".")

    # Value before CGPA/GPA label
    m = re.search(r"(?i)\b([0-9](?:[\.,][0-9]{1,2})?)\b\s*(?:/\s*10(?:[\.,]0{1,2})?\s*)?(?:cgpa|gpa|sgpa)\b", joined_cgpa)
    if m:
        return _clean_value(m.group(1)).replace(",", ".")

    # Percentage without '%'
    m = re.search(r"(?i)\b(?:percentage|percent|marks|aggregate)\b\s*[:\-]?\s*([0-9]{1,3}(?:[\.,][0-9]{1,2})?)\b", joined_cgpa)
    if m:
        return _clean_value(m.group(1)).replace(",", ".") + "%"

    # Spaced labels (C G P A, S G P A)
    label = r"(?:c\s*\.?\s*g\s*\.?\s*p\s*\.?\s*a|s\s*\.?\s*g\s*\.?\s*p\s*\.?\s*a|g\s*\.?\s*p\s*\.?\s*a)"
    val10 = r"(10(?:[\.,]0{1,2})?|[0-9](?:[\.,][0-9]{1,2})?)"

    m = re.search(rf"(?i){label}\s*[:\-]?\s*{val10}(?:\s*/\s*10(?:[\.,]0{{1,2}})?)?", joined_cgpa)
    if m:
        return _clean_value(m.group(1)).replace(",", ".")

    m = re.search(rf"(?i)\b{val10}\b\s*(?:/\s*10(?:[\.,]0{{1,2}})?\s*)?{label}", joined_cgpa)
    if m:
        return _clean_value(m.group(1)).replace(",", ".")

    return ""


def extract_education(text: str) -> Education:
    """Extract education information from resume text.

    Prioritizes higher education (B.Tech, M.Tech, etc.) over school education.
    For same degree level, prefers Present/Current timeline, then highest year.

    Args:
        text: Raw resume text

    Returns:
        Education object with extracted information
    """
    # Find education section
    edu_sec_regex = re.compile(
        r"(?:^|\n)\s*(EDUCATION|ACADEMICS|ACADEMIC QUALIFICATIONS|EDUCATIONAL QUALIFICATIONS)\s*:?[\t ]*\n(.*?)(?=\n\s*(?:EXPERIENCE|WORK EXPERIENCE|PROJECTS|CERTIFICATIONS|SKILLS|ACHIEVEMENTS|PUBLICATIONS|LANGUAGES|INTERESTS|HOBBIES|AWARDS)\b|$)",
        re.IGNORECASE | re.DOTALL,
    )
    edu_match = edu_sec_regex.search(text)
    edu_block = edu_match.group(2) if edu_match else text

    # Split into entries by degree keywords
    lines = edu_block.splitlines()
    degree_lines = [i for i, line in enumerate(lines) if DEGREE_PAT.search(line)]

    entries = []
    if degree_lines:
        for idx, degree_line_num in enumerate(degree_lines):
            prev_boundary = degree_lines[idx - 1] + 1 if idx > 0 else 0
            is_higher = _is_higher_degree(lines[degree_line_num])

            start = degree_line_num
            for back in (1, 2, 3, 4):
                cand = degree_line_num - back
                if cand < prev_boundary or cand < 0:
                    break
                prev_ln = lines[cand].strip()
                if not prev_ln or DEGREE_PAT.search(prev_ln):
                    break
                if is_higher and (_is_school_degree(prev_ln) or "junior" in prev_ln.lower()):
                    break
                start = cand

            end = degree_lines[idx + 1] if idx + 1 < len(degree_lines) else len(lines)
            entry_text = "\n".join(lines[start:end]).strip()
            if entry_text:
                entries.append(entry_text)
    else:
        entries = [ch.strip() for ch in re.split(r"\n\s*\n+", edu_block) if ch.strip()]

    if not entries:
        entries = [edu_block]

    logger.debug(f"Found {len(entries)} education entries to evaluate")

    # Select best entry
    best: Optional[Dict[str, str]] = None
    best_year: int = -1
    has_present: bool = False
    best_degree_level: int = 0

    for entry in entries:
        fields = _parse_education_entry(entry)
        is_present = bool(re.search(r"\b(present|current)\b", entry.lower()))
        degree_level = _get_degree_level(entry)

        try:
            y = int(fields["passout_year"]) if fields["passout_year"] else -1
        except ValueError:
            y = -1

        should_update = False
        if degree_level > best_degree_level:
            should_update = True
        elif degree_level == best_degree_level:
            if is_present and not has_present:
                should_update = True
            elif is_present and has_present and y > best_year:
                should_update = True
            elif not is_present and not has_present and y > best_year:
                should_update = True

        if should_update:
            best_year = y
            best = fields
            has_present = is_present
            best_degree_level = degree_level

    if best:
        return Education(
            college_name=best.get("college_name", ""),
            department=best.get("department", ""),
            cgpa=best.get("cgpa", ""),
            passout_year=best.get("passout_year", ""),
        )

    # Fallback
    fields = _parse_education_entry(edu_block)
    return Education(
        college_name=fields.get("college_name", ""),
        department=fields.get("department", ""),
        cgpa=fields.get("cgpa", ""),
        passout_year=fields.get("passout_year", ""),
    )
