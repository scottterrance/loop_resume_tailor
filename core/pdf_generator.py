"""
PDF Generator: converts a plain-text tailored resume into a
professionally formatted, ATS-compatible PDF using WeasyPrint (HTML→PDF).

Fixes applied:
- No more "?" symbols: pre-processing cleans encoding artifacts
- Fragmented header reconstruction: reassembles pdfminer-scattered contact lines
- Line-joining: continuation lines (from pdfminer word-wrap) are rejoined
- No excessive spacing: precise CSS layout control
- Projects and all sections preserved via robust section detection
- Clean, recruiter-ready layout
"""

import os
import re
import uuid
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


# ── Constants ─────────────────────────────────────────────────────────────────

SECTION_KEYWORDS = [
    "SUMMARY", "PROFESSIONAL SUMMARY", "OBJECTIVE", "PROFILE",
    "EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE", "EMPLOYMENT HISTORY",
    "SKILLS", "TECHNICAL SKILLS", "CORE COMPETENCIES", "COMPETENCIES", "KEY SKILLS",
    "EDUCATION", "ACADEMIC BACKGROUND", "ACADEMIC HISTORY",
    "PROJECTS", "KEY PROJECTS", "PERSONAL PROJECTS", "NOTABLE PROJECTS", "SIDE PROJECTS",
    "CERTIFICATIONS", "CERTIFICATES", "LICENSES", "CREDENTIALS",
    "AWARDS", "HONORS", "ACHIEVEMENTS", "ACCOMPLISHMENTS",
    "PUBLICATIONS", "VOLUNTEER", "LANGUAGES", "INTERESTS", "ACTIVITIES",
]

DATE_PATTERN = re.compile(
    r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec'
    r'|January|February|March|April|June|July|August|September|October|November|December)'
    r'|\b(20\d{2}|19\d{2})\b'
    r'|Present|Current|Now',
    re.IGNORECASE
)

CONTACT_PATTERN = re.compile(
    r'@|linkedin\.com|github\.com|\(\d{3}\)|\d{3}[-.\s]\d{4}'
    r'|\.com|\.net|\.org|\.io'
    r'|\b(NC|CA|TX|NY|FL|WA|GA|VA|MA|CO|IL|OH|PA|AZ|NV|OR|MN|MI|MO|TN|SC|MD|IN|WI|KY|AL|LA|MS|AR|OK|KS|NE|IA|UT|NM|ID|MT|WY|ND|SD|AK|HI|DC|Remote)\b',
    re.IGNORECASE
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def html_escape(text: str) -> str:
    return (text
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;'))


def is_section_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    upper = stripped.upper()
    return any(upper == kw or upper.startswith(kw) for kw in SECTION_KEYWORDS)


def is_bullet(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and stripped[0] in ('-', '•', '*', '·', '–')


def looks_like_continuation(line: str) -> bool:
    """
    Return True if this line looks like a continuation of the previous line
    (i.e. it was word-wrapped by pdfminer and should be joined).
    Heuristics:
    - Does not start with a bullet, section keyword, or capital letter that starts a new sentence
    - Does not contain a date pattern (not a job header line)
    - Is not a standalone short token (like a separator)
    """
    stripped = line.strip()
    if not stripped:
        return False
    if is_bullet(stripped):
        return False
    if is_section_header(stripped):
        return False
    if DATE_PATTERN.search(stripped) and '|' in stripped:
        return False  # looks like a job header
    # If it starts with a lowercase letter or continuation words, it's a continuation
    if stripped[0].islower():
        return True
    # If it's a very short fragment (< 4 words) and doesn't look like a new sentence start
    words = stripped.split()
    if len(words) <= 3 and not stripped.endswith('.') and not stripped[0].isupper():
        return True
    return False


# ── Text Pre-processing ───────────────────────────────────────────────────────

def normalize_unicode(text: str) -> str:
    """Replace Unicode/encoding artifacts with ASCII equivalents."""
    # Strip markdown bold/italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)

    replacements = {
        '\u2013': '-',    # en dash
        '\u2014': ' - ',  # em dash
        '\u2018': "'",    # left single quote
        '\u2019': "'",    # right single quote
        '\u201c': '"',    # left double quote
        '\u201d': '"',    # right double quote
        '\u2022': '-',    # bullet
        '\u00b7': '-',    # middle dot
        '\u2026': '...',  # ellipsis
        '\u00a0': ' ',    # non-breaking space
        '\u200b': '',     # zero-width space
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def join_wrapped_lines(lines: list[str]) -> list[str]:
    """
    Join lines that were word-wrapped by pdfminer back into full logical lines.
    
    Strategy:
    - Bullet lines: join continuation lines until the next bullet, blank line,
      section header, or job-header line.
    - Regular lines: join if the current line ends without terminal punctuation
      and the next line starts with lowercase or is a short fragment.
    """
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        # Empty line: preserve as paragraph break
        if not stripped:
            result.append('')
            i += 1
            continue

        # Section headers: never join
        if is_section_header(stripped):
            result.append(stripped)
            i += 1
            continue

        # Bullet line: aggressively join continuation lines
        if is_bullet(stripped):
            combined = stripped
            while i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if not next_line:
                    # Blank line: peek ahead to see if the next non-empty line is a
                    # lowercase continuation (pdfminer sometimes inserts blank lines mid-bullet)
                    if not combined.endswith(('.', '!', '?', ':')):
                        # Look for next non-empty line
                        peek = i + 2
                        while peek < len(lines) and not lines[peek].strip():
                            peek += 1
                        if peek < len(lines):
                            peek_line = lines[peek].strip()
                            # If it starts with lowercase and is not a bullet/section/job-header,
                            # skip the blank line and join
                            if (peek_line
                                    and peek_line[0].islower()
                                    and not is_section_header(peek_line)
                                    and not is_bullet(peek_line)
                                    and not (DATE_PATTERN.search(peek_line) and '|' in peek_line)):
                                i += 1  # skip the blank line
                                continue
                    break  # blank line ends the bullet
                if is_section_header(next_line):
                    break
                if is_bullet(next_line):
                    break  # next bullet starts
                # If next line looks like a job header (has date + pipe), stop
                if DATE_PATTERN.search(next_line) and '|' in next_line:
                    break
                # If next line looks like a job title (short, no period, followed by date)
                # we don't have look-ahead here, so use heuristic: if it's ALL CAPS-ish
                # and short, stop
                if len(next_line) < 60 and next_line[0].isupper() and not next_line[0].islower():
                    # Could be a new job title — check if it ends with period
                    # If it doesn't end with period and is short, it might be a title
                    # Be conservative: only stop if it looks like a name/title pattern
                    words = next_line.split()
                    if len(words) <= 6 and not next_line.endswith((',', ';')):
                        # Check if it's a continuation by looking at whether current ends incomplete
                        if combined.endswith(('.', '!', '?', ':')):
                            break
                        # If it starts with a capital and current ends with a comma or semicolon,
                        # it's likely a continuation
                        if combined.endswith((',', ';')):
                            combined = combined + ' ' + next_line
                            i += 1
                            continue
                        # Otherwise treat as new entry
                        break
                # Join the continuation
                combined = combined + ' ' + next_line
                i += 1
            result.append(combined)
            i += 1
            continue

        # Regular (non-bullet) line: join if ends incomplete and next starts lower
        # or current line ends with a preposition/conjunction (common pdfminer wrap point)
        HANGING_WORDS = {
            'with', 'and', 'or', 'for', 'in', 'on', 'at', 'to', 'of', 'by',
            'the', 'a', 'an', 'as', 'via', 'using', 'from', 'into', 'across',
            'including', 'such', 'both', 'their', 'its', 'our', 'your',
        }
        combined = stripped
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not next_line:
                break
            if is_section_header(next_line) or is_bullet(next_line):
                break
            if DATE_PATTERN.search(next_line) and '|' in next_line:
                break
            ends_incomplete = not combined.endswith(('.', '!', '?', ':'))
            next_starts_lower = next_line and next_line[0].islower()
            next_is_fragment = len(next_line.split()) <= 4 and not DATE_PATTERN.search(next_line)
            # Also join if the current line ends with a hanging preposition/conjunction
            last_word = combined.rstrip().split()[-1].lower().rstrip(',;') if combined.strip() else ''
            ends_with_hanging = last_word in HANGING_WORDS

            if ends_incomplete and (next_starts_lower or next_is_fragment or ends_with_hanging):
                combined = combined + ' ' + next_line
                i += 1
            else:
                break

        result.append(combined)
        i += 1

    return result


def preprocess_resume(text: str) -> str:
    """
    Full pre-processing pipeline for extracted resume text.
    """
    text = normalize_unicode(text)

    lines = text.split('\n')

    # Step 1: Strip each line, replace " ? " separators
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # Replace " ? " with " | " (encoding artifact for em-dash or pipe)
        if len(stripped) < 120 and ' ? ' in stripped:
            stripped = stripped.replace(' ? ', ' | ')
        cleaned.append(stripped)

    # Step 2: Join word-wrapped continuation lines
    joined = join_wrapped_lines(cleaned)

    # Step 3: Collapse multiple blank lines
    result = []
    prev_blank = False
    for line in joined:
        if not line.strip():
            if not prev_blank:
                result.append('')
            prev_blank = True
        else:
            result.append(line)
            prev_blank = False

    return '\n'.join(result).strip()


# ── Header Reconstruction ─────────────────────────────────────────────────────

def reconstruct_header(header_lines: list[str]) -> tuple[str, str, str]:
    """
    Given raw header lines (potentially fragmented), return (name, title, contact_string).
    
    The pdfminer output for a typical resume header looks like:
      Line 0: "Senior AI Engineer | Application Development"  (title - first line extracted)
      Line 1: "MICHAEL THORPE"                                (name - ALL CAPS)
      Lines 2+: fragmented contact info
    
    Strategy: find the ALL CAPS line as the name, treat the first non-contact line
    before it as the title, and everything else as contact.
    """
    if not header_lines:
        return ("Resume", "", "")

    # Filter out empty and separator-only lines
    non_empty = [l.strip() for l in header_lines if l.strip() and l.strip() not in ('|', '-', '/', ',', '–')]

    name = ""
    title = ""
    contact_parts = []

    # First pass: find the ALL CAPS name line
    name_idx = -1
    for idx, line in enumerate(non_empty):
        is_contact = bool(CONTACT_PATTERN.search(line))
        is_date = bool(DATE_PATTERN.search(line))
        if not is_contact and not is_date and line.isupper() and not is_section_header(line):
            name = line
            name_idx = idx
            break

    # If no ALL CAPS name found, use first non-contact line
    if not name:
        for idx, line in enumerate(non_empty):
            is_contact = bool(CONTACT_PATTERN.search(line))
            is_date = bool(DATE_PATTERN.search(line))
            if not is_contact and not is_date:
                name = line
                name_idx = idx
                break

    # Second pass: classify remaining lines
    for idx, line in enumerate(non_empty):
        if idx == name_idx:
            continue
        is_contact = bool(CONTACT_PATTERN.search(line))
        is_date = bool(DATE_PATTERN.search(line))
        is_sep = line in ('|', '-', '/', ',')
        if is_sep:
            continue
        if is_contact or is_date or re.search(r'\d{3}', line):
            contact_parts.append(line)
        elif not title and idx < name_idx and len(line) < 80:
            # Lines before the name are typically the job title
            title = line
        elif not title and idx > name_idx and len(line) < 80 and not is_contact:
            title = line
        else:
            contact_parts.append(line)

    # Clean and deduplicate contact parts
    clean_contact = []
    seen = set()
    for part in contact_parts:
        part = part.strip().strip('|').strip()
        if part and part not in ('|', '-', '/', ',') and part not in seen:
            seen.add(part)
            clean_contact.append(part)

    contact_str = " | ".join(clean_contact)
    return (name or "Resume", title, contact_str)


# ── CSS ───────────────────────────────────────────────────────────────────────

CSS = """
@page {
    size: letter;
    margin: 0.6in 0.65in 0.6in 0.65in;
}

* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: "DejaVu Serif", Georgia, "Times New Roman", serif;
    font-size: 10pt;
    line-height: 1.4;
    color: #111;
}

.resume-name {
    text-align: center;
    font-size: 20pt;
    font-weight: bold;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 3pt;
}

.resume-title {
    text-align: center;
    font-size: 10.5pt;
    color: #333;
    margin-bottom: 3pt;
    font-style: italic;
}

.contact-line {
    text-align: center;
    font-size: 9pt;
    color: #333;
    margin-bottom: 10pt;
}

.section-header {
    font-size: 11pt;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    border-bottom: 1.2pt solid #111;
    padding-bottom: 1.5pt;
    margin-top: 10pt;
    margin-bottom: 4pt;
}

.job-block {
    margin-bottom: 6pt;
}

.job-title {
    font-weight: bold;
    font-size: 10pt;
    margin-bottom: 1pt;
}

.job-meta {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 2pt;
}

.job-company {
    font-size: 9.5pt;
    color: #333;
    font-style: italic;
}

.job-date {
    font-size: 9pt;
    color: #444;
    white-space: nowrap;
    margin-left: 8pt;
    flex-shrink: 0;
}

ul.bullets {
    margin: 2pt 0 2pt 14pt;
    padding: 0;
    list-style-type: disc;
}

ul.bullets li {
    margin-bottom: 1.5pt;
    font-size: 9.5pt;
    line-height: 1.35;
}

p.body-line {
    font-size: 9.5pt;
    margin-bottom: 2pt;
    line-height: 1.4;
}
"""


# ── HTML Resume Builder ───────────────────────────────────────────────────────

def build_html(resume_text: str) -> str:
    """
    Parse plain-text resume and build a clean HTML document for WeasyPrint.
    """
    resume_text = preprocess_resume(resume_text)
    lines = resume_text.split('\n')

    # ── Extract header block ──────────────────────────────────────────────────
    header_lines = []
    body_start = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if is_section_header(stripped):
            body_start = i
            break
        header_lines.append(stripped)
        body_start = i + 1

    name, title_line, contact_str = reconstruct_header(header_lines)

    header_html = f'<div class="resume-name">{html_escape(name)}</div>\n'
    if title_line:
        header_html += f'<div class="resume-title">{html_escape(title_line)}</div>\n'
    if contact_str:
        header_html += f'<div class="contact-line">{html_escape(contact_str)}</div>\n'

    # ── Build body ────────────────────────────────────────────────────────────
    body_lines = lines[body_start:]
    body_html = ""
    i = 0
    current_bullets: list[str] = []

    def flush_bullets() -> str:
        nonlocal current_bullets
        if not current_bullets:
            return ""
        items = "".join(
            f"<li>{html_escape(b.lstrip('-•*·– ').strip())}</li>"
            for b in current_bullets
        )
        current_bullets = []
        return f'<ul class="bullets">{items}</ul>\n'

    while i < len(body_lines):
        line = body_lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            body_html += flush_bullets()
            i += 1
            continue

        if is_section_header(stripped):
            body_html += flush_bullets()
            body_html += f'<div class="section-header">{html_escape(stripped)}</div>\n'
            i += 1
            continue

        if is_bullet(stripped):
            current_bullets.append(stripped)
            i += 1
            continue

        body_html += flush_bullets()

        # Look ahead for company/date line to detect job title
        next_stripped = ""
        j = i + 1
        while j < len(body_lines) and not body_lines[j].strip():
            j += 1
        if j < len(body_lines):
            next_stripped = body_lines[j].strip()

        is_job_title = (
            len(stripped) < 80
            and not stripped.endswith('.')
            and not is_section_header(stripped)
            and not is_bullet(stripped)
            and bool(DATE_PATTERN.search(next_stripped) if next_stripped else False)
        )

        if is_job_title:
            body_html += '<div class="job-block">\n'
            body_html += f'<div class="job-title">{html_escape(stripped)}</div>\n'
            i += 1
            while i < len(body_lines) and not body_lines[i].strip():
                i += 1
            if i < len(body_lines):
                company_line = body_lines[i].strip()
                parts = [p.strip() for p in company_line.split('|')]
                if len(parts) >= 2 and DATE_PATTERN.search(parts[-1]):
                    company_info = " | ".join(parts[:-1])
                    date_info = parts[-1]
                    body_html += (
                        f'<div class="job-meta">'
                        f'<span class="job-company">{html_escape(company_info)}</span>'
                        f'<span class="job-date">{html_escape(date_info)}</span>'
                        f'</div>\n'
                    )
                else:
                    body_html += f'<div class="job-company">{html_escape(company_line)}</div>\n'
                i += 1
            body_html += '</div>\n'
            continue

        body_html += f'<p class="body-line">{html_escape(stripped)}</p>\n'
        i += 1

    body_html += flush_bullets()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
{CSS}
</style>
</head>
<body>
{header_html}
{body_html}
</body>
</html>"""
    return html


# ── Public API ────────────────────────────────────────────────────────────────

def generate_pdf(resume_text: str, candidate_name: str = "resume") -> str:
    """
    Convert plain-text resume to a professionally formatted PDF using WeasyPrint.
    Returns the path to the generated PDF file.
    """
    from weasyprint import HTML

    file_id = str(uuid.uuid4())[:8]
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', candidate_name)[:30]
    output_path = OUTPUT_DIR / f"{safe_name}_{file_id}.pdf"

    html_content = build_html(resume_text)

    html_debug_path = OUTPUT_DIR / f"{safe_name}_{file_id}.html"
    html_debug_path.write_text(html_content, encoding='utf-8')

    HTML(string=html_content).write_pdf(str(output_path))
    return str(output_path)


def get_output_path(file_id: str) -> str | None:
    """Find an output file by partial ID."""
    for f in OUTPUT_DIR.iterdir():
        if file_id in f.name and f.suffix == '.pdf':
            return str(f)
    return None
