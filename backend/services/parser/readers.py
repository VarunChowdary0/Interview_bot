"""File readers for PDF and DOCX resume files."""

import logging
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from .models import FileType


logger = logging.getLogger(__name__)


def clean_extracted_text(text: str) -> str:
    """Clean up text extracted from PDF/DOCX files.

    Removes common artifacts from PDF extraction:
    - Page numbers and footers
    - Excessive pipe characters from column layouts
    - Standalone date lines and reattaches them
    - Multiple blank lines

    Args:
        text: Raw extracted text

    Returns:
        Cleaned text
    """
    lines = text.split('\n')
    cleaned_lines = []

    for i, line in enumerate(lines):
        line = line.strip()

        # Skip empty lines (we'll add proper spacing later)
        if not line:
            if cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines.append('')
            continue

        # Skip page number footers like "email@example.com 1 / 2"
        if re.match(r'^[\w.+-]+@[\w.-]+\s+\d+\s*/\s*\d+$', line):
            continue

        # Skip standalone page numbers
        if re.match(r'^\d+\s*/\s*\d+$', line) or re.match(r'^Page\s+\d+', line, re.IGNORECASE):
            continue

        # Clean lines that are just pipes
        if re.match(r'^[\|\s]+$', line):
            continue

        # Remove excessive pipes (more than 2 in a row)
        line = re.sub(r'\|{2,}', ' ', line)

        # Clean up pipe-separated content (common in PDF columns)
        # Convert "item1 | item2 | item3" to proper format
        if line.count('|') > 3 and len(line) < 50:
            # This is likely a separator line, skip it
            continue

        # Handle standalone date lines - try to attach to previous line
        date_pattern = r'^(\d{2}/\d{4})\s*[–\-—]\s*(\d{2}/\d{4}|Present|Current)$'
        if re.match(date_pattern, line, re.IGNORECASE):
            if cleaned_lines and cleaned_lines[-1]:
                # Attach date to previous line
                cleaned_lines[-1] = cleaned_lines[-1] + ' ' + line
                continue

        # Handle "Month Year - Month Year" date lines
        month_date_pattern = r'^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{4}\s*[–\-—]\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec|Present|Current)[a-z]*\s*\d{0,4}$'
        if re.match(month_date_pattern, line, re.IGNORECASE):
            if cleaned_lines and cleaned_lines[-1]:
                cleaned_lines[-1] = cleaned_lines[-1] + ' ' + line
                continue

        # Clean up location/date suffixes like "2026 | Hyderabad, Telangana"
        line = re.sub(r'\s*\|\s*', ' | ', line)  # Normalize pipe spacing

        cleaned_lines.append(line)

    # Join lines and clean up multiple spaces
    result = '\n'.join(cleaned_lines)
    result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 consecutive newlines
    result = re.sub(r' {2,}', ' ', result)  # Max 1 space

    return result.strip()


def detect_file_type(file_path: str) -> Optional[FileType]:
    """Detect file type from extension.

    Args:
        file_path: Path to the file

    Returns:
        FileType enum or None if unsupported
    """
    path = Path(file_path)
    ext = path.suffix.lower()

    if ext == '.pdf':
        return FileType.PDF
    elif ext in ('.docx', '.doc'):
        return FileType.DOCX
    elif ext == '.txt':
        return FileType.TXT

    return None


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file.

    Uses PyPDF2 as primary extractor, falls back to pdfplumber.

    Args:
        file_path: Path to the PDF file

    Returns:
        Extracted text or empty string on failure
    """
    # Try PyPDF2 first
    try:
        import PyPDF2

        text = ""
        with open(file_path, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                extracted = page.extract_text() or ""
                text += extracted + "\n"

        if text.strip():
            return text
    except ImportError:
        logger.warning("PyPDF2 not installed, trying pdfplumber")
    except Exception as e:
        logger.warning(f"PyPDF2 failed: {e}, trying pdfplumber")

    # Fallback to pdfplumber
    try:
        import pdfplumber

        text = ""
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                extracted = page.extract_text() or ""
                text += extracted + "\n"
        return text
    except ImportError:
        logger.error("Neither PyPDF2 nor pdfplumber installed")
        return ""
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""


def extract_text_from_docx(file_path: str) -> str:
    """Extract text from a DOCX file.

    Parses the DOCX (which is a ZIP) and extracts text from word/document.xml.
    No external dependencies required beyond standard library.

    Args:
        file_path: Path to the DOCX file

    Returns:
        Extracted text or empty string on failure
    """
    try:
        if not zipfile.is_zipfile(file_path):
            logger.warning(f"File is not a valid DOCX (zip) file: {file_path}")
            return ""

        with zipfile.ZipFile(file_path) as z:
            if "word/document.xml" not in z.namelist():
                logger.warning(f"DOCX missing word/document.xml: {file_path}")
                return ""

            xml_content = z.read("word/document.xml")

            try:
                tree = ET.fromstring(xml_content)
            except ET.ParseError as e:
                logger.error(f"Failed to parse DOCX XML: {e}")
                return ""

            # WordprocessingML namespace
            ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
            texts = [t.text for t in tree.findall('.//w:t', ns) if t.text]
            return "\n".join(texts)

    except Exception as e:
        logger.error(f"Error extracting text from DOCX: {e}")
        return ""


def extract_text_from_txt(file_path: str) -> str:
    """Extract text from a plain text file.

    Args:
        file_path: Path to the text file

    Returns:
        File contents or empty string on failure
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read()
    except UnicodeDecodeError:
        # Try with different encoding
        try:
            with open(file_path, 'r', encoding='latin-1') as f:
                return f.read()
        except Exception as e:
            logger.error(f"Error reading text file: {e}")
            return ""
    except Exception as e:
        logger.error(f"Error reading text file: {e}")
        return ""


def extract_text(file_path: str, clean: bool = True) -> str:
    """Extract text from a file based on its type.

    Automatically detects file type and uses appropriate extractor.

    Args:
        file_path: Path to the file
        clean: Whether to clean up PDF artifacts (default True)

    Returns:
        Extracted text or empty string on failure

    Raises:
        ValueError: If file type is not supported
    """
    file_type = detect_file_type(file_path)

    if file_type is None:
        raise ValueError(f"Unsupported file type: {file_path}")

    text = ""
    if file_type == FileType.PDF:
        text = extract_text_from_pdf(file_path)
    elif file_type == FileType.DOCX:
        text = extract_text_from_docx(file_path)
    elif file_type == FileType.TXT:
        text = extract_text_from_txt(file_path)

    if clean and text:
        text = clean_extracted_text(text)

    return text
