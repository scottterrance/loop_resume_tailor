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

def clean_markdown(text: str) -> str:
    """Remove markdown bold/italic symbols for PDF rendering."""
    text = re.sub(r'\*\*(.*?)\*\*', r'\1', text)  # Bold
    text = re.sub(r'__(.*?)__', r'\1', text)      # Bold
    text = re.sub(r'\*(.*?)\*', r'\1', text)      # Italic
    text = re.sub(r'_(.*?)_', r'\1', text)        # Italic
    return text

def generate_pdf(resume_text: str, candidate_name: str = "resume") -> str:
    """
    Convert plain-text resume to a professionally formatted PDF using fpdf2.
    Returns the output file path.
    """
    file_id = str(uuid.uuid4())[:8]
    safe_name = re.sub(r'[^a-zA-Z0-9_-]', '_', candidate_name)[:30]
    output_path = OUTPUT_DIR / f"{safe_name}_{file_id}.pdf"

    pdf = ResumePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    # Page width minus margins
    effective_width = pdf.w - 2 * pdf.l_margin
    
    # Use a standard serif font for ATS readability
    pdf.set_font("Times", size=10)
    
    lines = resume_text.strip().split('\n')
    
    header_processed = False
    for line in lines:
        line = clean_markdown(line.strip())
        if not line:
            pdf.ln(2)
            continue
            
        # First non-empty line is the name
        if not header_processed:
            pdf.set_font("Times", "B", 16)
            pdf.cell(0, 10, line, ln=True, align='C')
            pdf.set_font("Times", size=10)
            header_processed = True
            continue

        # Check for section headers (all caps or specific keywords)
        upper_line = line.upper()
        section_keywords = ["SUMMARY", "EXPERIENCE", "SKILLS", "EDUCATION", "PROJECTS", "CERTIFICATIONS", "PROFESSIONAL EXPERIENCE"]
        is_header = any(kw in upper_line for kw in section_keywords) and len(line) < 50
        
        if is_header:
            pdf.ln(4)
            pdf.set_font("Times", "B", 11)
            pdf.cell(0, 7, line, ln=True)
            pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(2)
            pdf.set_font("Times", size=10)
        elif line.startswith(("-", "•", "*")):
            # Bullet points with safe indentation
            bullet_indent = 5
            pdf.set_x(pdf.l_margin + bullet_indent)
            # Use multi_cell with a calculated width to ensure it fits
            pdf.multi_cell(effective_width - bullet_indent, 5, line)
        else:
            # Normal text
            pdf.multi_cell(0, 5, line)

    pdf.output(str(output_path))
    return str(output_path)

def get_output_path(file_id: str) -> str | None:
    """Find an output file by partial ID."""
    for f in OUTPUT_DIR.iterdir():
        if file_id in f.name and f.suffix == '.pdf':
            return str(f)
    return None
