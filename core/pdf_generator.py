"""
PDF Generator: converts a plain-text tailored resume into a
professionally formatted, ATS-compatible PDF using fpdf (v1.7.2).

Fixes applied:
- Compatible: Uses fpdf 1.7.2 (standard in many environments).
- ASCII-Safe: Normalizes all Unicode characters to ASCII to prevent '?' and crashes.
- Smarter Header: Reconstructs fragmented headers from pdfminer output.
- Line-Joining: Joins word-wrapped continuation lines and paragraph fragments.
- ATS-Friendly: Clean, single-column layout with standard fonts.
"""

import os
import re
import uuid
from pathlib import Path
from fpdf import FPDF

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

def is_section_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 60:
        return False
    upper = stripped.upper()
    return any(upper == kw or upper.startswith(kw) for kw in SECTION_KEYWORDS)


def is_bullet(line: str) -> bool:
    stripped = line.strip()
    return bool(stripped) and stripped[0] in ('-', '•', '*', '·', '–')


# ── Text Pre-processing ───────────────────────────────────────────────────────

def normalize_to_ascii(text: str) -> str:
    """Replace Unicode characters with ASCII equivalents to prevent fpdf crashes."""
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
    
    # Final sweep: replace any remaining non-ASCII with space
    return text.encode('ascii', 'ignore').decode('ascii')


def join_wrapped_lines(lines: list[str]) -> list[str]:
    HANGING_WORDS = {
        'with', 'and', 'or', 'for', 'in', 'on', 'at', 'to', 'of', 'by',
        'the', 'a', 'an', 'as', 'via', 'using', 'from', 'into', 'across',
        'including', 'such', 'both', 'their', 'its', 'our', 'your',
    }
    
    result = []
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            result.append('')
            i += 1
            continue

        if is_section_header(stripped):
            result.append(stripped)
            i += 1
            continue

        # Bullet line: join continuation lines
        if is_bullet(stripped):
            combined = stripped
            while i + 1 < len(lines):
                next_line = lines[i + 1].strip()
                if not next_line:
                    peek = i + 2
                    while peek < len(lines) and not lines[peek].strip():
                        peek += 1
                    if peek < len(lines):
                        peek_line = lines[peek].strip()
                        if peek_line and peek_line[0].islower() and not is_bullet(peek_line) and not is_section_header(peek_line):
                            i = peek - 1
                            continue
                    break
                if is_section_header(next_line) or is_bullet(next_line):
                    break
                combined = combined + ' ' + next_line
                i += 1
            result.append(combined)
            i += 1
            continue

        # Regular line: join if ends incomplete or hanging
        combined = stripped
        while i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if not next_line or is_section_header(next_line) or is_bullet(next_line):
                break
            
            ends_incomplete = not combined.endswith(('.', '!', '?', ':'))
            next_starts_lower = next_line and next_line[0].islower()
            words = combined.rstrip().split()
            last_word = words[-1].lower().rstrip(',;') if words else ''
            ends_with_hanging = last_word in HANGING_WORDS
            
            if ends_incomplete and (next_starts_lower or ends_with_hanging):
                combined = combined + ' ' + next_line
                i += 1
            else:
                break
        
        result.append(combined)
        i += 1
    
    return result


def preprocess_resume(text: str) -> str:
    text = normalize_to_ascii(text)
    lines = [l.strip() for l in text.split('\n')]
    joined = join_wrapped_lines(lines)
    
    res = []
    prev_blank = False
    for l in joined:
        if not l.strip():
            if not prev_blank:
                res.append('')
            prev_blank = True
        else:
            res.append(l)
            prev_blank = False
    return '\n'.join(res).strip()


# ── Header Reconstruction ─────────────────────────────────────────────────────

def reconstruct_header(header_lines: list[str]) -> tuple[str, str, str]:
    non_empty = [l.strip() for l in header_lines if l.strip() and l.strip() not in ('|', '-', '/', ',', '–')]
    name, title, contact_parts = "", "", []
    
    name_idx = -1
    for idx, line in enumerate(non_empty):
        if line.isupper() and not is_section_header(line) and not CONTACT_PATTERN.search(line):
            name = line
            name_idx = idx
            break
    
    if not name and non_empty:
        name = non_empty[0]
        name_idx = 0
        
    for idx, line in enumerate(non_empty):
        if idx == name_idx: continue
        if CONTACT_PATTERN.search(line) or re.search(r'\d{3}', line):
            contact_parts.append(line)
        elif not title and len(line) < 80:
            title = line
        else:
            contact_parts.append(line)
            
    contact_str = " | ".join(list(dict.fromkeys(contact_parts)))
    return (name or "Resume", title, contact_str)


# ── PDF Class ─────────────────────────────────────────────────────────────────

class ResumePDF(FPDF):
    def __init__(self):
        super(ResumePDF, self).__init__(orientation='P', unit='mm', format='Letter')
        self.set_margins(16, 15, 16)
        self.set_auto_page_break(auto=True, margin=15)

    def header_block(self, name, title, contact):
        self.set_font("Times", "B", 18)
        self.cell(0, 10, name, ln=1, align='C')
        
        if title:
            self.set_font("Times", "I", 11)
            self.cell(0, 6, title, ln=1, align='C')
            
        if contact:
            self.set_font("Times", "", 9)
            self.multi_cell(0, 5, contact, align='C')
        
        self.ln(4)

    def section_title(self, label):
        self.set_font("Times", "B", 11)
        self.cell(0, 8, label.upper(), ln=1)
        curr_y = self.get_y() - 1
        self.line(self.l_margin, curr_y, 216 - self.r_margin, curr_y)
        self.ln(2)

    def job_header(self, title, company_date):
        self.set_font("Times", "B", 10)
        self.cell(0, 5, title, ln=1)
        
        if company_date:
            if '|' in company_date:
                parts = [p.strip() for p in company_date.split('|')]
                company = " | ".join(parts[:-1])
                date = parts[-1]
                
                self.set_font("Times", "I", 9.5)
                self.cell(140, 5, company, ln=0)
                self.set_font("Times", "", 9)
                self.cell(0, 5, date, ln=1, align='R')
            else:
                self.set_font("Times", "I", 9.5)
                self.cell(0, 5, company_date, ln=1)
        self.ln(1)

    def bullet_point(self, text):
        self.set_font("Times", "", 9.5)
        self.set_x(self.l_margin + 2)
        self.cell(3, 5, "-", ln=0)
        text = text.lstrip('-•*·– ').strip()
        self.multi_cell(0, 5, text)
        self.ln(0.5)

    def body_text(self, text):
        self.set_font("Times", "", 9.5)
        self.multi_cell(0, 5, text)
        self.ln(1)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_pdf(resume_text: str, candidate_name: str = "resume") -> str:
    resume_text = preprocess_resume(resume_text)
    lines = resume_text.split('\n')
    
    header_lines = []
    body_start = 0
    for i, line in enumerate(lines):
        if is_section_header(line):
            body_start = i
            break
        header_lines.append(line)
        body_start = i + 1
    
    name, title_line, contact_str = reconstruct_header(header_lines)
    
    pdf = ResumePDF()
    pdf.add_page()
    pdf.header_block(name, title_line, contact_str)
    
    body_lines = lines[body_start:]
    i = 0
    while i < len(body_lines):
        line = body_lines[i].strip()
        if not line:
            i += 1
            continue
            
        if is_section_header(line):
            pdf.section_title(line)
            i += 1
            continue
            
        if is_bullet(line):
            pdf.bullet_point(line)
            i += 1
            continue
            
        next_line = ""
        j = i + 1
        while j < len(body_lines) and not body_lines[j].strip(): j += 1
        if j < len(body_lines): next_line = body_lines[j].strip()
        
        is_job = (len(line) < 80 and not line.endswith('.') and DATE_PATTERN.search(next_line))
        if is_job:
            pdf.job_header(line, next_line)
            i = j + 1
            continue
            
        pdf.body_text(line)
        i += 1

    file_id = str(uuid.uuid4())[:8]
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', candidate_name)[:30]
    output_path = OUTPUT_DIR / f"{safe_name}_{file_id}.pdf"
    
    pdf.output(str(output_path), 'F')
    return str(output_path)

def get_output_path(file_id: str) -> str | None:
    for f in OUTPUT_DIR.iterdir():
        if file_id in f.name and f.suffix == '.pdf':
            return str(f)
    return None
