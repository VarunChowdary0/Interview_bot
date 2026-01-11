"""Professional summary/objective extraction from resume text."""

import re


def extract_summary(text: str) -> str:
    """Extract professional summary or objective from resume text.

    Looks for summary/objective section at the beginning of the resume.

    Args:
        text: Raw resume text

    Returns:
        Summary text or empty string if not found
    """
    # Look for explicit summary/objective section
    summary_match = re.search(
        r'(?:^|\n)\s*(?:SUMMARY|PROFESSIONAL SUMMARY|OBJECTIVE|CAREER OBJECTIVE|'
        r'PROFILE|ABOUT ME?|OVERVIEW|CAREER SUMMARY|PROFESSIONAL PROFILE)\s*:?[\t ]*\n'
        r'(.*?)(?=\n\s*(?:EDUCATION|SKILLS|EXPERIENCE|WORK|EMPLOYMENT|'
        r'PROJECTS?|CERTIFICATIONS?|ACHIEVEMENTS?|TECHNICAL|CONTACT|'
        r'CODING\s*PROFILE)\b|$)',
        text,
        re.IGNORECASE | re.DOTALL,
    )

    if summary_match:
        summary_text = summary_match.group(1).strip()
        # Clean up the summary
        # Remove bullet points if present
        lines = summary_text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            # Remove leading bullets
            line = re.sub(r'^[\s•\-*>◦○▪▸]+', '', line).strip()
            if line:
                cleaned_lines.append(line)

        # Join lines into paragraph
        summary = ' '.join(cleaned_lines)
        # Clean up multiple spaces
        summary = re.sub(r'\s+', ' ', summary).strip()

        # Limit length to avoid capturing too much
        if len(summary) > 1000:
            # Try to cut at sentence boundary
            sentences = re.split(r'(?<=[.!?])\s+', summary)
            summary = ''
            for sentence in sentences:
                if len(summary) + len(sentence) < 1000:
                    summary += sentence + ' '
                else:
                    break
            summary = summary.strip()

        return summary

    # Fallback: Look for a paragraph at the very beginning (after name/contact)
    # This handles resumes without explicit section headers
    lines = text.split('\n')
    potential_summary = []
    started = False
    contact_passed = False

    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            if started and potential_summary:
                break
            continue

        # Skip initial contact info lines (email, phone, links)
        if re.search(r'@|linkedin|github|phone|mobile|\+\d{1,3}', line, re.IGNORECASE):
            contact_passed = True
            continue

        # Skip name line (usually first non-empty line)
        if i < 3 and len(line.split()) <= 4 and not any(c.isdigit() for c in line):
            continue

        # If we hit a section header, stop
        if re.match(r'^[A-Z\s]{2,}:?\s*$', line) or re.match(r'^(?:EDUCATION|SKILLS|EXPERIENCE)\b', line, re.IGNORECASE):
            break

        # Check if this looks like a summary paragraph
        if contact_passed and len(line) > 50 and not line.startswith(('•', '-', '*', '>')):
            started = True
            potential_summary.append(line)
        elif started:
            if len(line) > 30 and not line.startswith(('•', '-', '*', '>')):
                potential_summary.append(line)
            else:
                break

    if potential_summary:
        summary = ' '.join(potential_summary)
        summary = re.sub(r'\s+', ' ', summary).strip()
        if len(summary) > 100:  # Minimum length to be considered a summary
            return summary[:1000] if len(summary) > 1000 else summary

    return ""
