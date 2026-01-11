"""Contact information extraction (name, email, phone) from resume text."""

import re
from typing import List, Optional

from .models import ContactInfo


# Email pattern constants
_EMAIL_PATTERN = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
_EMAIL_RE = re.compile(_EMAIL_PATTERN)


def extract_email(text: str) -> str:
    """Extract email address from resume text.

    Handles common PDF extraction artifacts where contact labels get glued to the
    local-part (e.g., 'P E' becoming 'pe' prefix).

    Args:
        text: Raw resume text

    Returns:
        Extracted email address or empty string
    """
    if not text:
        return ""

    candidates: List[str] = []

    # Look for labeled emails first
    for m in re.finditer(
        rf"(?i)(?:^|\n)\s*(?:e-?mail|email)\s*[:\-\u2013\u2014]?\s*({_EMAIL_PATTERN})",
        text,
    ):
        candidates.append(m.group(1))

    # Then find all email patterns
    candidates.extend(_EMAIL_RE.findall(text))
    candidates = [c.strip() for c in candidates if c and c.strip()]

    if not candidates:
        return ""

    # De-dupe while preserving order
    seen = set()
    ordered: List[str] = []
    for c in candidates:
        key = c.strip().lower()
        if key not in seen:
            seen.add(key)
            ordered.append(c)

    # Handle 'pe' prefix artifact (from 'P E' label)
    lowered = {c.strip().lower() for c in ordered}
    for c in ordered:
        lc = c.strip().lower()
        if lc.startswith("pe") and len(lc) > 4:
            clean = lc[2:]
            if clean in lowered and _EMAIL_RE.fullmatch(clean):
                return clean

    # Normalize and pick the first good match
    for c in ordered:
        fixed = _normalize_email_candidate(c, text)
        if fixed and _EMAIL_RE.fullmatch(fixed):
            return fixed

    return ordered[0].strip().lower()


def _normalize_email_candidate(email: str, text: str) -> str:
    """Normalize an email candidate, handling common PDF artifacts."""
    if not email:
        return ""

    e = email.strip().lower().strip("\"'<>[](){}.,;:")
    e = re.sub(r"\s+", "", e)

    # Fix 'P E' (Personal Email) label artifact
    if e.startswith("pe") and len(e) > 4:
        candidate = e[2:]
        if _EMAIL_RE.fullmatch(candidate):
            # Check for label correlation in text
            if re.search(
                rf"(?i)(?:^|[^a-z0-9_])p\s*\.?\s*e\s*[:\-\u2013\u2014]?\s*{re.escape(candidate)}",
                text or "",
            ):
                return candidate

            low = (text or "").lower()
            idx = low.find(e)
            if idx != -1:
                ctx = low[max(0, idx - 80):idx]
                if re.search(r"\bp\s*\.?\s*e\b", ctx) or re.search(r"\bp\s*\.?\s*e\s*[:\-]", ctx):
                    return candidate
                if re.search(r"\bphone\b.*\bemail\b", ctx):
                    return candidate

            # If clean candidate appears separately, prefer it
            if re.search(rf"(?i)(?<![\w.+-]){re.escape(candidate)}(?![\w.+-])", text or ""):
                return candidate

    return e


def extract_phone(text: str) -> str:
    """Extract and normalize phone number to 10 digits.

    Strategy:
    - Prefer contiguous 10-digit sequences
    - Then look for country-code patterns (+91, 00xx)
    - Finally, generic number-like sequences

    Args:
        text: Raw resume text

    Returns:
        Normalized 10-digit phone number or empty string
    """
    usep = r"[\s.\-‑–—()]*"

    # Country code pattern
    m = re.search(rf"(?:\+|00){usep}\d{{1,3}}(?:{usep}\d){{10,}}", text)
    if m:
        return _normalize_phone(m.group(0))

    # Contiguous 10 digits
    m = re.search(r"(?<!\d)(\d{10})(?!\d)", text)
    if m:
        return _normalize_phone(m.group(1))

    # Generic long number sequence
    m = re.search(r"\d(?:[\d\s.\-‑–—()]{8,})\d", text)
    if m:
        norm = _normalize_phone(m.group(0))
        if norm:
            return norm

    return ""


def _normalize_phone(num_str: Optional[str]) -> str:
    """Normalize a phone string to 10 digits."""
    if not num_str:
        return ""

    digits = re.sub(r"\D", "", num_str)

    if len(digits) == 12:
        return digits[-10:]
    if len(digits) >= 10:
        return digits[-10:]

    return ""


def extract_name(text: str) -> str:
    """Extract candidate name from resume text.

    Uses multiple strategies:
    1. Pattern matching for Title Case names at start
    2. Label-based patterns (Name: ...)
    3. Heuristic from first lines (handles ALL CAPS)

    Args:
        text: Raw resume text

    Returns:
        Extracted name or empty string
    """
    # Try Title Case pattern at start
    name_pattern = r'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})'
    name_match = re.search(name_pattern, text)
    if name_match:
        return name_match.group(1)

    # Try label-based pattern
    name_label_match = re.search(
        r'(?:^|\n)(?:Name|NAME)[:\s]+([A-Za-z][A-Za-z\.-]+(?:\s+[A-Za-z\.-]+){1,3})',
        text
    )
    if name_label_match:
        return name_label_match.group(1).strip()

    # Fallback to heuristic extraction
    return _extract_name_heuristic(text)


def _extract_name_heuristic(text: str) -> str:
    """Heuristic to extract candidate name from first lines.

    - Skips lines containing email/phone/digits
    - Accepts 2-4 tokens made of letters/.-
    - Handles ALL-CAPS names by normalizing to Title Case
    """
    try:
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        for line in lines[:6]:
            if '@' in line or any(ch.isdigit() for ch in line):
                continue

            words = [w for w in re.split(r"\s+", line) if w]
            if 2 <= len(words) <= 4:
                if not all(re.match(r"^[A-Za-z\.-]+$", w) for w in words):
                    continue

                all_caps = all(w.isupper() for w in words)
                title_like = all(re.match(r"^[A-Z][a-z]+$", w) for w in words)

                if all_caps or title_like:
                    if all_caps:
                        return " ".join(w.capitalize() for w in words)
                    return " ".join(words)
        return ""
    except Exception:
        return ""


def extract_contact_info(text: str) -> ContactInfo:
    """Extract all contact information from resume text.

    Args:
        text: Raw resume text

    Returns:
        ContactInfo object with name, email, and phone
    """
    return ContactInfo(
        name=extract_name(text),
        email=extract_email(text),
        phone=extract_phone(text),
    )
