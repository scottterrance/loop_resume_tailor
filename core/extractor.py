"""
Resume text extractor: handles PDF and plain text input.
"""

import io
from pathlib import Path


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract text from a PDF file using pdfminer.six."""
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(io.BytesIO(file_bytes))
        return text.strip()
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def extract_text_from_file(file_path: str) -> str:
    """Extract text from a file (PDF or text)."""
    path = Path(file_path)
    if path.suffix.lower() == '.pdf':
        with open(file_path, 'rb') as f:
            return extract_text_from_pdf(f.read())
    else:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read().strip()


def clean_resume_text(text: str) -> str:
    """Clean and normalize resume text."""
    import re
    # Normalize multiple spaces within lines (common in pdfminer output)
    lines = text.split('\n')
    lines = [re.sub(r' {2,}', ' ', line) for line in lines]
    text = '\n'.join(lines)
    # Remove excessive blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    # Remove non-printable characters (but preserve newlines)
    text = re.sub(r'[^\x20-\x7E\n]', ' ', text)
    # Clean up spaces left by non-printable removal
    lines = text.split('\n')
    lines = [re.sub(r' {2,}', ' ', line).strip() for line in lines]
    text = '\n'.join(lines)
    return text.strip()
