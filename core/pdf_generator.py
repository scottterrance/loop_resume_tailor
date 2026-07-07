"""
PDF Generator: converts a plain-text tailored resume into a
professionally formatted, ATS-compatible PDF using fpdf2.
"""

import os
import re
import uuid
from pathlib import Path
from fpdf import FPDF

OUTPUT_DIR = Path(__file__).parent.parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

class ResumePDF(FPDF):
    def header(self):
        pass

    def footer(self):
        pass

def clean_text(text: str) -> str:
    """Remove markdown symbols and normalize characters for PDF rendering."""
    # Remove markdown bold/italic
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)
    text = re.sub(r'__(.*?)__', r'\1', text)
    text = re.sub(r'\*(.*?)\*', r'\1', text)
    text = re.sub(r'_(.*?)_', r'\1', text)
    
    # Normalize unicode characters that might break fpdf2
    text = text.encode('latin-1', 'replace').decode('latin-1')
    return text

def generate_pdf(resume_text: str, candidate_name: str = "resume") -> str:
    """
    Convert plain-text resume to a professionally formatted PDF using fpdf2.
    Uses a 'Safe-Wrap' approach to prevent horizontal space errors.
    """
    file_id = str(uuid.uuid4())[:8]
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', candidate_name)[:30]
    output_path = OUTPUT_DIR / f"{safe_name}_{file_id}.pdf"

    pdf = ResumePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Define safe margins
    margin_l = 20
    margin_r = 20
    pdf.set_left_margin(margin_l)
    pdf.set_right_margin(margin_r)
    
    # Use a standard serif font for ATS readability
    pdf.set_font("Times", size=10)
    
    # Calculate safe width manually
    safe_width = pdf.w - margin_l - margin_r
    
    lines = resume_text.strip().split('\n')
    
    header_processed = False
    for line in lines:
        line = clean_text(line.strip())
        if not line:
            pdf.ln(3)
            continue
            
        # First non-empty line is the name
        if not header_processed:
            pdf.set_font("Times", "B", 18)
            pdf.cell(safe_width, 10, line, ln=True, align='C')
            pdf.set_font("Times", size=10)
            header_processed = True
            continue

        # Check for section headers
        upper_line = line.upper()
        section_keywords = ["SUMMARY", "EXPERIENCE", "SKILLS", "EDUCATION", "PROJECTS", "CERTIFICATIONS", "PROFESSIONAL EXPERIENCE"]
        is_header = any(kw in upper_line for kw in section_keywords) and len(line) < 50
        
        if is_header:
            pdf.ln(5)
            pdf.set_font("Times", "B", 12)
            pdf.cell(safe_width, 8, line, ln=True)
            pdf.line(pdf.get_x(), pdf.get_y(), pdf.get_x() + safe_width, pdf.get_y())
            pdf.ln(2)
            pdf.set_font("Times", size=10)
        elif line.startswith(("-", "•", "*")):
            # Bullet points with manual safe indentation
            pdf.set_x(margin_l + 5)
            # multi_cell handles wrapping within the given width
            pdf.multi_cell(safe_width - 5, 5, line)
        else:
            # Normal text with full width
            pdf.set_x(margin_l)
            pdf.multi_cell(safe_width, 5, line)

    pdf.output(str(output_path))
    return str(output_path)

def get_output_path(file_id: str) -> str | None:
    """Find an output file by partial ID."""
    for f in OUTPUT_DIR.iterdir():
        if file_id in f.name and f.suffix == '.pdf':
            return str(f)
    return None
